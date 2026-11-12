/* Load the shared FeatureHub SDK only after the visitor opens feedback. */
( function () {
	'use strict';
	function bindFeedback() {
		var trigger = document.getElementById( 'wikiapiary-feedback' );
		var loading = false;
		var ready = false;
		// Older cached page HTML may predate the native tab. Upgrade only this
		// optional control so deploying feedback never requires flushing wiki pages.
		if ( !trigger && document.body.classList.contains( 'skin-foreground' ) && window.parent === window ) {
			trigger = document.createElement( 'a' );
			trigger.id = 'wikiapiary-feedback';
			trigger.className = 'hide-for-print';
			trigger.href = 'https://featurehub.dobriy.ai/embed/wikiapiary';
			trigger.setAttribute( 'role', 'button' );
			trigger.setAttribute( 'aria-haspopup', 'dialog' );
			trigger.setAttribute( 'aria-expanded', 'false' );
			trigger.title = 'Suggest a feature or report a bug';
			var sourceLogo = document.querySelector( '.top-bar-logo' );
			if ( sourceLogo ) {
				var logo = sourceLogo.cloneNode();
				logo.removeAttribute( 'class' );
				logo.alt = '';
				logo.width = 28;
				logo.height = 28;
				trigger.appendChild( logo );
			}
			var label = document.createElement( 'span' );
			label.textContent = 'Feedback';
			trigger.appendChild( label );
			document.body.appendChild( trigger );
		}
		if ( !trigger || trigger.dataset.bound ) {
			return;
		}
		if ( window.parent !== window ) {
			trigger.remove();
			return;
		}
		trigger.dataset.bound = 'true';
		trigger.addEventListener( 'keydown', function ( event ) {
			if ( event.key === ' ' ) {
				event.preventDefault();
				trigger.click();
			}
		} );
		trigger.addEventListener( 'click', function ( event ) {
			if ( event.ctrlKey || event.metaKey || event.shiftKey || event.altKey ) {
				return;
			}
			event.preventDefault();
			if ( ready ) {
				window.FeatureHub.open();
				return;
			}
			if ( loading ) {
				return;
			}
			loading = true;
			trigger.setAttribute( 'aria-busy', 'true' );
			var script = document.createElement( 'script' );
			script.src = 'https://featurehub.dobriy.ai/widget.js';
			script.dataset.app = 'wikiapiary';
			script.dataset.context = 'off';
			script.async = true;
			function fallback() {
				clearTimeout( timer );
				trigger.removeAttribute( 'aria-busy' );
				window.location.assign( trigger.href );
			}
			var timer = setTimeout( fallback, 15000 );
			script.onerror = fallback;
			script.onload = function () {
				var shadow = document.getElementById( 'featurehub-widget' )?.shadowRoot;
				if ( !shadow || !window.FeatureHub ) {
					fallback();
					return;
				}
				clearTimeout( timer );
				trigger.removeAttribute( 'aria-busy' );
				var style = document.createElement( 'style' );
				style.textContent = '.tab{display:none!important}' +
					'.shade{background:#20242b55}.panel{border:1px solid #dfe3e8;border-radius:10px;background:#fff}' +
					'.panel iframe{border:0;border-radius:0;box-shadow:none}' +
					'.panel-actions{background:#fff5cc;border-color:#dfe3e8;font-family:Inter,system-ui,sans-serif;color:#20242b}' +
					'.panel-actions a{color:#925800}.panel-actions button{background:#fff;color:#20242b;border-color:#c9ced6;border-radius:6px;min-height:44px}' +
					':focus-visible{outline:3px solid #f5b700;outline-offset:2px}' +
					'.hint{background:#fff5cc;color:#20242b;border-color:#f5b700}.rect{border-color:#925800;background:#f5b70022}' +
					'@media(max-width:520px){.panel{border:0;border-radius:0}}';
				shadow.appendChild( style );
				var dialog = shadow.querySelector( 'dialog' );
				new MutationObserver( function () {
					trigger.setAttribute( 'aria-expanded', dialog.open ? 'true' : 'false' );
				} ).observe( dialog, { attributes: true, attributeFilter: [ 'open' ] } );
				ready = true;
				window.FeatureHub.open();
			};
			document.head.appendChild( script );
		} );
	}
	if ( document.readyState === 'loading' ) {
		document.addEventListener( 'DOMContentLoaded', bindFeedback );
	} else {
		bindFeedback();
	}
}() );
