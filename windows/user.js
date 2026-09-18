// VerticalFox - Firefox 157 compatibility prefs
// The old sidebar (#sidebar-box) is display:none unless native vertical tabs
// are enabled (see browser-shared.css @media not -moz-pref("sidebar.verticalTabs")).
user_pref("sidebar.verticalTabs", true);
// Keep the sidebar permanently open so the collapsed 40px strip always shows
// (instead of Firefox's own "expand-on-hover"/"hide-on-close" launcher logic).
user_pref("sidebar.visibility", "always-show");
// Required for userChrome.css to load at all.
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
