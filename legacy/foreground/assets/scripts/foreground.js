jQuery(document).ready(function() {

  function bindExplicitDropdown(buttonSelector, menuSelector, namespace) {
    var $button = jQuery(buttonSelector);
    var $menu = jQuery(menuSelector);
    var $item = $button.closest('li.has-dropdown');

    if (!$button.length || !$menu.length || !$item.length) {
      return;
    }

    function positionMenu() {
      $menu.css({
        position: 'absolute',
        left: '',
        top: '',
        width: 'auto',
        height: 'auto',
        clip: 'auto',
        overflow: 'visible',
        display: 'block'
      });
    }

    function closeMenu() {
      $item.removeClass('hover');
      $menu.removeClass('open').attr('aria-hidden', 'true').css({
        display: 'none',
        width: '1px',
        height: '1px',
        clip: 'rect(1px, 1px, 1px, 1px)',
        overflow: 'hidden',
        left: '-9999px',
        top: ''
      });
      $button.removeClass('open').attr('aria-expanded', 'false');
    }

    function openMenu() {
      $item.addClass('hover');
      positionMenu();
      $menu.addClass('open').attr('aria-hidden', 'false').css({
        display: 'block'
      });
      $button.addClass('open').attr('aria-expanded', 'true');
    }

    closeMenu();

    $button.off('click.' + namespace).on('click.' + namespace, function (e) {
      e.preventDefault();
      e.stopPropagation();

      if ($menu.hasClass('open')) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    jQuery(document).off('click.' + namespace).on('click.' + namespace, function (e) {
      if (!jQuery(e.target).closest(buttonSelector + ', ' + menuSelector).length) {
        closeMenu();
      }
    });

    jQuery(window).off('resize.' + namespace).on('resize.' + namespace, function () {
      if ($menu.hasClass('open')) {
        positionMenu();
      }
    });
  }

  // Log errors
  jQuery(document).foundation(function (response) {
    if (window.console) console.log(response.errors);
  });

  // Foundation's legacy dropdown wiring is unreliable on the migrated stack.
  // Keep key menus working with explicit positioning/toggle fallbacks.
  bindExplicitDropdown('#actions-button', '#actions', 'foregroundActions');
  bindExplicitDropdown('#toolbox-button', '#toolbox-dropdown', 'foregroundToolbox');
  bindExplicitDropdown('#personal-tools-button', '#personal-tools-menu', 'foregroundPersonalTools');
  
  // The Echo extension puts an item in personal tools that Foreground really should have in the top menu
  // to make this easier, we move it here and loaded earlier to speed up transform
  jQuery("#pt-notifications").prependTo("#echo-notifications-alerts");
  jQuery("#pt-notifications-message").prependTo("#echo-notifications-messages");
  jQuery("#pt-notifications-alert").prependTo("#echo-notifications-alerts");
  jQuery("#pt-notifications-notice").prependTo("#echo-notifications-notice");

  // Turn categories into labels
  jQuery('#mw-normal-catlinks ul li a').addClass('label');

});
