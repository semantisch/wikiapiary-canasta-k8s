#!/bin/sh
set -eu
apt-get update
php_packages=$(dpkg-query -W -f='${binary:Package} ${db:Status-Status}\n' 'php8.2-*' | awk '$2 == "installed" { print $1 }')
test -n "$php_packages"
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --only-upgrade $php_packages
dpkg --compare-versions "$(dpkg-query -W -f='${Version}' php8.2-common)" ge '8.2.35-1~deb12u1'
php -r 'if (version_compare(PHP_VERSION, "8.2.35", "<")) { exit(1); }'
for php_conf in /etc/php/8.2/*/conf.d; do
    test -d "$php_conf" || continue
    printf '%s\n' '; PHP advisory 2026-10-23 / CVE-2026-115560' 'session.upload_progress.enabled=0' > "$php_conf/zz-security-20261024.ini"
done
php-fpm8.2 --test
apt-get clean
rm -rf /var/lib/apt/lists/*
