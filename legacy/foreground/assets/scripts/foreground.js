jQuery(document).ready(function() {

  // Log errors
  jQuery(document).foundation(function (response) {
    if (window.console) console.log(response.errors);
  });

  // Foundation's legacy dropdown wiring is unreliable on the migrated stack.
  // Keep the page actions menu working with a small compatibility fallback.
  var $actionsButton = jQuery('#actions-button');
  var $actionsMenu = jQuery('#actions');

  function positionActionsMenu() {
    if (!$actionsButton.length || !$actionsMenu.length) {
      return;
    }

    var offset = $actionsButton.offset();
    $actionsMenu.css({
      position: 'absolute',
      left: offset.left,
      top: offset.top + $actionsButton.outerHeight() + 8
    });
  }

  function closeActionsMenu() {
    $actionsMenu.removeClass('open').attr('aria-hidden', 'true');
    $actionsButton.removeClass('open');
  }

  function openActionsMenu() {
    positionActionsMenu();
    $actionsMenu.addClass('open').attr('aria-hidden', 'false');
    $actionsButton.addClass('open');
  }

  if ($actionsButton.length && $actionsMenu.length) {
    $actionsMenu.attr('aria-hidden', 'true');

    $actionsButton.on('click.foregroundActions', function (e) {
      e.preventDefault();
      e.stopPropagation();

      if ($actionsMenu.hasClass('open')) {
        closeActionsMenu();
      } else {
        openActionsMenu();
      }
    });

    jQuery(document).on('click.foregroundActions', function (e) {
      if (!jQuery(e.target).closest('#actions, #actions-button').length) {
        closeActionsMenu();
      }
    });

    jQuery(window).on('resize.foregroundActions', function () {
      if ($actionsMenu.hasClass('open')) {
        positionActionsMenu();
      }
    });
  }
  
  // The Echo extension puts an item in personal tools that Foreground really should have in the top menu
  // to make this easier, we move it here and loaded earlier to speed up transform
  jQuery("#pt-notifications").prependTo("#echo-notifications-alerts");
  jQuery("#pt-notifications-message").prependTo("#echo-notifications-messages");
  jQuery("#pt-notifications-alert").prependTo("#echo-notifications-alerts");
  jQuery("#pt-notifications-notice").prependTo("#echo-notifications-notice");

  // Turn categories into labels
  jQuery('#mw-normal-catlinks ul li a').addClass('label');

});
