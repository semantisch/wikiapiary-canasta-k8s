vcl 4.0;

# Borrowed from mediawiki.org/wiki/Manual:Varnish_caching
# and modified for Canasta

backend default {
    .host = "web";
    .port = "80";
    .first_byte_timeout = 120s;
    .connect_timeout = 30s;
    .between_bytes_timeout = 120s;
}

acl purge {
    "localhost";
    "127.0.0.1";
    "::1";
    "10.42.0.0"/16;
}

# vcl_recv is called whenever a request is received
sub vcl_recv {
    # Serve objects up to 2 minutes past their expiry if the backend
    # is slow to respond.
    set req.grace = 1h;

    set req.http.X-Forwarded-For = req.http.X-Forwarded-For + ", " + client.ip;

    set req.backend_hint= default;

    # This uses the ACL action called "purge". Basically if a request to
    # PURGE the cache comes from anywhere other than localhost, ignore it.
    if (req.method == "PURGE") {
        if (!client.ip ~ purge) {
            return (synth(405, "Not allowed."));
        } else {
            return (purge);
        }
    }

    # Pass sitemaps
    if (req.url ~ "\.xml(\.gz)?$") {
        return (pass);
    }

    # Pass images
    if (req.url ~ "/w/images/") {
        return(pass);
    }

    # Pass parsoid
    if (req.url ~ "/w/rest.php/") {
        return(pass);
    }

    # Pass API
    if (req.url ~ "/w/api.php") {
        return(pass);
    }

    # Bypass cache for Special:Random
    if (req.url ~ "^/(w/index\.php\?title=|wiki/)Special:Random") {
        return (pass);
    }

    call mobile_detect;

    # Pass requests from logged-in users directly.
    if (req.http.Authorization) {
        return (pass);
    }

    # Preserve request cookies for non-idempotent and user-action flows such as
    # login and account forms. These must reach MediaWiki unchanged so the
    # submitted token matches the session that generated the form.
    if (req.method != "GET" && req.method != "HEAD") {
        return (pass);
    } /* We only cache GET and HEAD */

    # MediaWiki may set anonymous session cookies for public page views.
    # Those should not explode the shared cache or force a pass. Only keep
    # cookies that indicate an authenticated/user-specific session.
    if (req.http.Cookie) {
        if (req.http.Cookie ~ "(^|; )wikiapiary(UserID|UserName|Token)="
            || req.http.Cookie ~ "(^|; )centralauth_"
            || req.http.Cookie ~ "(^|; )Token=") {
            return (pass);
        }

        unset req.http.Cookie;
    }

    # Anonymous wiki pages should not explode into many cache variants based on
    # browser language preferences. Keep translated subpages keyed by URL, and
    # normalize everything else to the wiki's default anonymous interface
    # language so "en-US", plain "en", and no header all reuse one object.
    if (req.url ~ "^/wiki/" && req.url !~ "^/wiki/Special:") {
        if (req.url ~ "^/wiki/Main_Page/[A-Za-z0-9-]+$") {
            unset req.http.Accept-Language;
        } else {
            set req.http.Accept-Language = "en";
        }
    }

    # Force lookup if the request is a no-cache request from the client.
    if (req.http.Cache-Control ~ "no-cache") {
        ban(req.url);
    }

    # normalize Accept-Encoding to reduce vary
    if (req.http.Accept-Encoding) {
        if (req.http.User-Agent ~ "MSIE 6") {
        unset req.http.Accept-Encoding;
        } elsif (req.http.Accept-Encoding ~ "gzip") {
        set req.http.Accept-Encoding = "gzip";
        } elsif (req.http.Accept-Encoding ~ "deflate") {
        set req.http.Accept-Encoding = "deflate";
        } else {
        unset req.http.Accept-Encoding;
        }
    }

    return (hash);
}

# Canasta's farm selector only knows the canonical wiki hostname. Keep the
# original allowlisted Host on the client-side request (and therefore in
# Varnish's built-in cache key), but route backend fetches to the same Canasta
# wiki while carrying the requested mirror hostname in a trusted header.
sub vcl_backend_fetch {
    set bereq.http.X-WikiApiary-Request-Host = bereq.http.Host;
    set bereq.http.Host = "__PRIMARY_HOST__";
}

sub vcl_pipe {
        # Note that only the first request to the backend will have
        # X-Forwarded-For set.  If you use X-Forwarded-For and want to
        # have it set for all requests, make sure to have:
        # set req.http.connection = "close";

        # This is otherwise not necessary if you do not do any request rewriting.

        set req.http.connection = "close";
}

# Called if the cache has a copy of the page.
sub vcl_hit {
        set req.http.X-WikiApiary-Cache = "HIT";
        if (!obj.ttl > 0s) {
            return (pass);
        }
}

sub vcl_miss {
        set req.http.X-WikiApiary-Cache = "MISS";
        return (fetch);
}

sub vcl_pass {
        set req.http.X-WikiApiary-Cache = "PASS";
        return (fetch);
}

# Called after a document has been successfully retrieved from the backend.
sub vcl_backend_response {
        # Never retain error pages. In particular, a transient farm-routing 404
        # must not remain visible after routing is repaired.
        if (beresp.status >= 400) {
            set beresp.uncacheable = true;
            return (deliver);
        }

        set beresp.grace = 1h;

        # Respect the TTL MediaWiki sends via s-maxage rather than overriding it
        if (!beresp.ttl > 0s) {
          set beresp.uncacheable = true;
          return (deliver);
        }

        if (beresp.http.Set-Cookie) {
          # MediaWiki occasionally emits an anonymous session cookie on an
          # otherwise public wiki page. Strip that cookie so the page can stay
          # cacheable, but keep passing anything that looks user-specific.
          if ((bereq.url == "/" || bereq.url ~ "^/wiki/")
              && bereq.url !~ "^/wiki/Special:"
              && beresp.http.Set-Cookie ~ "wikiapiary_session="
              && beresp.http.Set-Cookie !~ "(UserID|UserName|Token|centralauth_)") {
            unset beresp.http.Set-Cookie;
          } else {
            set beresp.uncacheable = true;
            return (deliver);
          }
        }

        if (beresp.http.Authorization && !beresp.http.Cache-Control ~ "public") {
          set beresp.uncacheable = true;
          return (deliver);
        }

        if ((bereq.url == "/" || bereq.url ~ "^/wiki/") && bereq.url !~ "^/wiki/Special:" && beresp.http.Vary) {
          set beresp.http.Vary = regsub(beresp.http.Vary, "^Accept-Language,? ?", "");
          set beresp.http.Vary = regsub(beresp.http.Vary, ", ?Accept-Language$", "");
          set beresp.http.Vary = regsuball(beresp.http.Vary, ", ?Accept-Language, ?", ", ");
          if (beresp.http.Vary == "") {
            unset beresp.http.Vary;
          }
        }

        # Keep normal wiki pages around much longer at the proxy layer.
        # Freshness still comes from explicit purges on edit, so a longer TTL
        # helps hot landing/report pages stay warm instead of going cold again.
        if ((bereq.url == "/" || bereq.url ~ "^/wiki/") && bereq.url !~ "^/wiki/Special:" && beresp.ttl < 168h) {
          set beresp.ttl = 168h;
        }

        return (deliver);
}

# Rewrite Cache-Control before sending to browser
# Varnish has already used s-maxage internally; tell browsers not to cache at all
sub vcl_deliver {
    if (req.http.X-WikiApiary-Cache) {
        set resp.http.X-WikiApiary-Cache = req.http.X-WikiApiary-Cache;
    }

    if (resp.http.Cache-Control ~ "s-maxage") {
        set resp.http.Cache-Control = "public, max-age=60, stale-while-revalidate=300, stale-if-error=86400";

        # We strip anonymous cookies before hashing, so don't advertise Cookie
        # as a Vary dimension for public HTML responses.
        if (resp.http.Vary) {
            set resp.http.Vary = regsub(resp.http.Vary, "^Cookie,? ?", "");
            set resp.http.Vary = regsub(resp.http.Vary, ", ?Cookie$", "");
            set resp.http.Vary = regsuball(resp.http.Vary, ", ?Cookie, ?", ", ");
            if (resp.http.Vary == "") {
                unset resp.http.Vary;
            }
        }

        if ((req.url == "/" || req.url ~ "^/wiki/") && req.url !~ "^/wiki/Special:" && resp.http.Vary) {
            set resp.http.Vary = regsub(resp.http.Vary, "^Accept-Language,? ?", "");
            set resp.http.Vary = regsub(resp.http.Vary, ", ?Accept-Language$", "");
            set resp.http.Vary = regsuball(resp.http.Vary, ", ?Accept-Language, ?", ", ");
            if (resp.http.Vary == "") {
                unset resp.http.Vary;
            }
        }
    }
}

sub mobile_detect {
    set req.http.X-Device = "pc";

    if ( (req.http.User-Agent ~ "(?i)(mobi|240x240|240x320|320x320|alcatel|android|audiovox|bada|benq|blackberry|cdm-|compal-|docomo|ericsson|hiptop|htc[-_]|huawei|ipod|kddi-|kindle|meego|midp|mitsu|mmp\/|mot-|motor|ngm_|nintendo|opera.m|palm|panasonic|philips|phone|playstation|portalmmm|sagem-|samsung|sanyo|sec-|semc-browser|sendo|sharp|silk|softbank|symbian|teleca|up.browser|vodafone|webos)"
            || req.http.User-Agent ~ "^(?i)(lge?|sie|nec|sgh|pg)-" || req.http.Accept ~ "vnd.wap.wml")
        && req.http.User-Agent !~ "(SMART-TV.*SamsungBrowser)" )
    {
        set req.http.X-Device = "mobile";
    }
}
