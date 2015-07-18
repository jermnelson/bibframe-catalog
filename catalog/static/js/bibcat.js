var bfAgents = new Bloodhound({
  datumTokenizer: Bloodhound.tokenizers.obj.whitespace('agent'),
  queryTokenizer: Bloodhound.tokenizers.whitespace,
  remote: '/typeahead?q=%QUERY&type=Agent'
});


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
   this.uuid = search_result['uuid'];
   this.url = search_result['url'];
   this.title = search_result['title'];
   this.author = search_result['creators'];
   this.cover_url = '/static/images/cover-placeholder.png';
   if('cover' in search_result) {
     this.cover_url = search_result['cover']['src']; 
   } 
   this.held_items = []; 
   if('held_items' in search_result) {
       this.held_items = search_result['held_items'];
   }
}

function CatalogViewModel() {
	self = this;
	self.searchHeaders= ['All', 'Works',  'Instances','Agents','Topics'];
	self.sortOptions = ['Relevance','A-Z','Z-A','Category'];
	self.flash = ko.observable();
	self.from = ko.observable(0);
	self.queryPhrase = ko.observable();
	self.resultSummary = ko.observable();
	self.searchResults = ko.observableArray();
	self.shardSize = ko.observable(8);
	self.totalResults = ko.observable(0);
	self.csrf_token = $('#csrf_token').val();
	self.search_url = $('#search-url').val();
	self.chosenBfSearchViewId = ko.observable();
	self.chosenBfSortViewId = ko.observable();
	self.sortState = ko.computed(function() {
									return self.chosenBfSortViewId();    
								}, this);
	
    // Behaviours    
    self.goToBfSearchView = function(bfSearchView) { 
        location.hash = self.chosenBfSortViewId()+ "/" + bfSearchView;    

    };
	self.goToBfSortView = function(bfSortView) { 
        location.hash = bfSortView + "/" + self.chosenBfSearchViewId();
    };

	
	
	
	self.loadResults = function() {
		if(self.from() < self.totalResults()) { 
			self.searchCatalog();
		}
	}
	
	// Client-side routes    
    Sammy(function() {
        this.get('#:sort/:filter', function() {
            self.chosenBfSearchViewId(this.params.filter);
            self.chosenBfSortViewId(this.params.sort);
            //$.get("/mail", { mailId: this.params.mailId }, self.chosenMailData);
        });
        this.get('', function() { this.app.runRoute('get', '#Relevance/All') });
    }).run();



  self.searchCatalog = function() {

    var data = {
      csrfmiddlewaretoken: self.csrf_token,
      phrase: self.queryPhrase(),
      from: self.from(),
      size: self.shardSize() 
    }
    $.post(self.search_url, 
      data=data,
      function(datastore_response) {
        if(datastore_response['message'] == 'error') {
          self.flash(datastore_response['body']);
          self.resultSummary("Error with search!");
        } else {
          self.from(datastore_response['from']);
          if(datastore_response['total'] != self.totalResults()) {
              self.totalResults(datastore_response['total']);
          }
          if(self.from() > self.totalResults()){
              self.from(self.totalResults());
          }
          self.resultSummary(self.from() + " of " + self.totalResults() + ' for <em>' + self.queryPhrase() + "</em>");
          for(i in datastore_response['hits']) {
            var row = datastore_response['hits'][i];
            //if(row['uuid'] in window.localStorage) {
            //    continue;
            //}
            var result = new Result(row);
            self.searchResults.push(result);
            //window.localStorage.setItem(result['uuid'], JSON.stringify(result));
            //window.localStorage.setItem("counter:"+self.searchResults.length, result['uiid']);
          }
        }

     });
  }
}

	


