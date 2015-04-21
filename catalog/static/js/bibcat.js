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
  datumTokenizer: Bloodhound.tokenizers.obj.whitespace('topic'),
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
   var raw_result = search_result['_source'];
   console.log(raw_result);

   switch(raw_result) {
     case 'bf:instanceTitle' in raw_result:
        console.log("Found bf:instanceTitle" + raw_result['bf:instanceTitle'][0]);
        this.title = raw_result['bf:instanceTitle'][0]['bf:titleValue'];
        break;

     case 'bf:title':
        this.title = raw_result['bf:title'][0];
        break;

     case 'bf:titleStatement':
        this.title = raw_result['bf:titleStatement'][0];
        break;

     default:
       this.title = "Title unknown";
       break;
   }

   this.author = 'AUTHOR';
   this.locations = [];
}

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
    console.log("In search catalog " + self.searchResults.length + data['phrase']);
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


