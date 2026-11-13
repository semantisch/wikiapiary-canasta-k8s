/* Foreground interaction only. Presentation and labels are rendered by the skin. */
( function () {
	'use strict';

	function bindNavigation() {
		var toggle = document.querySelector( '.toggle-topbar > a' );
		var buttons = Array.from( document.querySelectorAll(
			'.top-bar-section .has-dropdown > a[aria-controls], #actions-button'
		) );

		function setOpen( button, open ) {
			var menu = document.getElementById( button.getAttribute( 'aria-controls' ) );
			var item = button.closest( 'li.has-dropdown' );
			var rect;
			if ( !menu ) {
				return;
			}
			button.setAttribute( 'aria-expanded', open ? 'true' : 'false' );
			button.classList.toggle( 'open', open );
			menu.setAttribute( 'aria-hidden', open ? 'false' : 'true' );
			menu.classList.toggle( 'open', open );
			if ( item ) {
				item.classList.toggle( 'hover', open );
			}
			if ( button.id === 'actions-button' && open ) {
				rect = button.getBoundingClientRect();
				menu.style.left = Math.max( 8, Math.min( rect.right - menu.offsetWidth, window.innerWidth - menu.offsetWidth - 8 ) ) + 'px';
				menu.style.top = ( rect.bottom + 8 ) + 'px';
				menu.style.maxHeight = Math.max( 0, window.innerHeight - rect.bottom - 16 ) + 'px';
			}
		}

		function closeAll( except ) {
			buttons.forEach( function ( button ) {
				if ( button !== except ) {
					setOpen( button, false );
				}
			} );
		}

		buttons.forEach( function ( button ) {
			button.addEventListener( 'click', function ( event ) {
				event.preventDefault();
				closeAll( button );
				setOpen( button, button.getAttribute( 'aria-expanded' ) !== 'true' );
			} );
			button.addEventListener( 'keydown', function ( event ) {
				if ( event.key === 'ArrowDown' ) {
					event.preventDefault();
					closeAll( button );
					setOpen( button, true );
					document.getElementById( button.getAttribute( 'aria-controls' ) ).querySelector( 'a' )?.focus();
				}
			} );
		} );
		document.addEventListener( 'click', function ( event ) {
			if ( !event.target.closest( '.top-bar-section .has-dropdown, #actions-button, #actions' ) ) {
				closeAll();
			}
		} );
		document.addEventListener( 'keydown', function ( event ) {
			if ( event.key === 'Escape' ) {
				var opened = buttons.find( function ( button ) { return button.getAttribute( 'aria-expanded' ) === 'true'; } );
				closeAll();
				if ( opened ) {
					opened.focus();
				}
			}
		} );
		window.addEventListener( 'resize', function () { closeAll(); } );
		window.addEventListener( 'scroll', function () {
			var actions = document.getElementById( 'actions-button' );
			if ( actions ) {
				setOpen( actions, false );
			}
		}, { passive: true } );
		if ( toggle ) {
			toggle.addEventListener( 'click', function ( event ) {
				var topBar = toggle.closest( '.top-bar' );
				if ( !topBar ) {
					return;
				}
				event.preventDefault();
				closeAll();
				toggle.setAttribute( 'aria-expanded', topBar.classList.toggle( 'expanded' ) ? 'true' : 'false' );
			} );
		}
	}

	if ( document.readyState === 'loading' ) {
		document.addEventListener( 'DOMContentLoaded', bindNavigation );
	} else {
		bindNavigation();
	}
}() );
