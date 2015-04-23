var bfAuthorities = new Bloodhound({
  datumTokenizer: Bloodhound.tokenizers.obj.whitespace('authority'),
  queryTokenizer: Bloodhound.tokenizers.whitespace,
  remote: '/typeahead?q=%QUERY&type=Authority'
});

var bfInstances = new Bloodhound({
  datumTokenizer: Bloodhound.tokenizers.obj.whitespace('instance'),
  queryTokenizer: Bloodhound.tokenizers.whitespace,
  remote: '/typeahead?q=%QUERY&type=Instance'
});

var bfPeople = new Bloodhound({
  datumTokenizer: Bloodhound.tokenizers.obj.whitespace('person'),
  queryTokenizer: Bloodhound.tokenizers.whitespace,
  remote: '/typeahead?q=%QUERY&type=Person'
 });


var bfTopics = new Bloodhound({
  datumTokenizer: Bloodhound.tokenizers.obj.nonword('topic'),
  queryTokenizer: Bloodhound.tokenizers.whitespace,
  remote: '/typeahead?q=%QUERY&type=Topic'
 });


var bfWorks = new Bloodhound({
  datumTokenizer: Bloodhound.tokenizers.obj.whitespace('work'),
  queryTokenizer: Bloodhound.tokenizers.whitespace,
  remote: '/typeahead?q=%QUERY&type=Work'
 });


 

var Result = function(search_result) {
   this.id = search_result['_id'];
   this.url = search_result['_type'] + '/' + this.id;
   var raw_result = search_result['_source'];

   this.title = raw_result['bf:titleStatement'];


   this.author = 'AUTHOR';
   this.locations = [];
}

// Using example from http://www.wiliam.com.au/wiliam-blog/twitters-typeahead-plugin-and-knockoutjs
ko.bindingHandlers.typeaheadJS = {
  init: function (element, valueAccessor, allBindingsAccessor) {
    var el = $(element);
    var options = ko.utils.unwrapObservable(valueAccessor());
    var allBindings = allBindingsAccessor();

    var data = new Bloodhound({
       datumTokenizer: Bloodhound.tokenizers.obj.whitespace(options.displayKey),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        limit: options.limit,
        prefetch: options.prefetch, // pass the options from the model to typeahead
        remote: options.remote // pass the options from the model to typeahead
     });

    // kicks off the loading/processing of 'local' and 'prefetch'
    initialize();

    el.attr("autocomplete", "off").typeahead(null, {
      name: options.name,
      displayKey: options.displayKey,
      // `ttAdapter` wraps the suggestion engine in an adapter that
      // is compatible with the typeahead jQuery plugin
      source: data.ttAdapter()

    }).on('typeahead:selected', function (obj, datum) {
       id(datum.id); // set the id observable when a user selects an option from the typeahead list
    });
   }
};

function CatalogViewModel() {
  self = this;
  self.flash = ko.observable();
  self.pageNumber = ko.observable(0);
  self.queryPhrase = ko.observable();
  self.searchResults = ko.observableArray();
  self.shardSize = ko.observable(8);

  self.searchCatalog = function() {
    var csrf_token = $('#csrf_token').val();
    var action = $('#search-url').val();
    console.log("queryPhrase is " + self.queryPhrase());
    var data = {
      csrfmiddlewaretoken: csrf_token,
      phrase: self.queryPhrase(),
      page: self.pageNumber()+self.shardSize()
    }
    $.post(action, 
      data=data,
      function(datastore_response) {
        
        if(datastore_response['message'] == 'error') {
          self.flash(datastore_response['body']);
        } else {
          for(i in datastore_response['hits']['hits']) {
            var row = datastore_response['hits']['hits'][i];
            self.searchResults.push(new Result(row));
          }
        }
       console.log("Finished search catalog " + self.searchResults().length);

     });
  }
}

	


