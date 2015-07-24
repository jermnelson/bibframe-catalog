	var catalog_view_model = new CatalogViewModel();
	ko.applyBindings(catalog_view_model);
	bibcat_format_searchToolbar();
	bibcat_launch_suggestbox();
 
 
  $(window).scroll(function() {
    if ($(window).scrollTop() + $(window).height() >= $(document).height()) {
       catalog_view_model.loadResults();
    }
  });
