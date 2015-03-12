
function CatalogViewModel() {
  self = this;
  self.flash = ko.observable();
  self.pageNumber(0);
  self.queryPhrase = ko.observable();
  self.searchResults = ko.observableArray();
  self.shardSize = ko.observable(8);

  self.searchCatalog = function() {
    var csrf_token = $('#csrf_token').val();
    var action = $('.form').attr('action');
    var data = {
      csrfmiddlewaretoken: csrf_token,
      q: self.searchQuery(),
      page: self.pageNumber()+self.shardSize()
    }
    $.post(action, 
      function(datastore_response) {
        if(datastore_response['message'] == 'error') {
          self.flash(datastore_response['body']);
        } else {
          for(i in datastore_response['results']) {
            var result = datastore_response['results'][i];
            self.searchResults.push(ResultViewModel(result));
          }
        }
     });
  }
}

function ResultViewModel(search_result) {
   self = this;
   self.title = search_result['titleValue'];
   self.locations = search_result['locations'];
}
