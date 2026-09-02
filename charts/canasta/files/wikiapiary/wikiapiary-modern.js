( function () {
	'use strict';

	function labelMenuButton( id, label ) {
		var button = document.getElementById( id );
		var icon;
		var text;

		if ( !button ) {
			return;
		}

		button.setAttribute( 'aria-label', label );
		button.setAttribute( 'aria-haspopup', 'true' );
		button.setAttribute( 'title', label );
		icon = button.querySelector( '.fa' );
		if ( icon ) {
			icon.setAttribute( 'aria-hidden', 'true' );
		}
		if ( !button.querySelector( '.wikiapiary-nav-label' ) ) {
			text = document.createElement( 'span' );
			text.className = 'wikiapiary-nav-label';
			text.textContent = label;
			button.appendChild( text );
		}
	}

	function enhanceNavigation() {
		var mobileToggle = document.querySelector( '.toggle-topbar > a' );
		var navigation = document.querySelector( '.top-bar-section' );

		labelMenuButton( 'toolbox-button', 'Tools' );
		labelMenuButton( 'personal-tools-button', 'Account' );
		document.querySelectorAll( '.top-bar-section .has-dropdown > a[aria-controls]' )
			.forEach( function ( button ) {
				button.setAttribute( 'aria-haspopup', 'true' );
			} );

		if ( mobileToggle && navigation ) {
			navigation.id = navigation.id || 'wikiapiary-navigation';
			mobileToggle.setAttribute( 'aria-controls', navigation.id );
			mobileToggle.setAttribute( 'aria-expanded', 'false' );
			mobileToggle.addEventListener( 'click', function ( event ) {
				var topBar = mobileToggle.closest( '.top-bar' );
				var expanded;

				if ( !topBar ) {
					return;
				}
				event.preventDefault();
				event.stopPropagation();
				expanded = topBar.classList.toggle( 'expanded' );
				mobileToggle.setAttribute( 'aria-expanded', expanded ? 'true' : 'false' );
			} );
		}
	}

	if ( document.readyState === 'loading' ) {
		document.addEventListener( 'DOMContentLoaded', enhanceNavigation );
	} else {
		enhanceNavigation();
	}
}() );
