function bibcat_launch_suggestbox (){
	bfAgents.initialize();
	bfInstances.initialize();
	bfWorks.initialize(); 
	bfTopics.initialize();
	$('#bf_typeahead .typeahead').typeahead(
	   {
			highlight: true
	   },
	   {
			name: 'bf-works',		
			displayKey: 'work',		
			source: bfWorks.ttAdapter(),	
			templates: {
						header: '<h3 class="bg-info">Works</h3>',
						footer: ''
						}
	   },
	   {
		  name: 'bf-instance',
		  displayKey: 'instance',
		  source: bfInstances.ttAdapter(),
		  templates: 	{
						   header: '<h3 class="bg-info">Instances</h3>',
						   footer: ''
						}
	   },
	   {
		  name: 'bf-agent',
		  displayKey: 'agent',
		  source: bfAgents.ttAdapter(),
		  templates:	{
						   header: '<h3 class="bg-info">Agents (People/Organizations)</h3>',
						   footer: ''
						}
	   },
	   {
		  name: 'bf-topics',
		  displayKey: 'topic',
		  source: bfTopics.ttAdapter(),
		  templates: 	{
							header: '<h3 class="bg-info">Topics</h3>',
							footer: ''
						}

		}
	).on('typeahead:selected', function (obj, datum) {
	 console.log("Typeahead selected is " + datum.uuid );
	 for (var key in datum) {
		 if (!(key=='uuid')) {
			 var itemType = key;
		 }
	}
	 window.location.replace("#item/" + itemType + "/" + datum.uuid);
	 bibcat_format_suggestbox();
	});
};
$("#bf_typeahead").find('input').keypress(function() {bibcat_format_suggestbox();});
$("#bf_typeahead").find('input').keydown(function() {bibcat_format_suggestbox();});
function bibcat_format_suggestbox() {
	$("div[class^='tt-dataset']").removeClass("tt-selectedDataSet");
	//$("div[class^='tt-dataset']").first().addClass("tt-selectedDataSet");
	$(".tt-suggestion.tt-cursor").closest("div[class^='tt-dataset']").addClass("tt-selectedDataSet");
	//$('#bf_typeahead .typeahead').find('typeahead:selected').closest("div[class^='tt-dataset']").addClass("tt-selectedDataSet");
};
$("div[class^='tt-dataset']").hover(function() {
	$(".tt-suggestion").removeClass("tt-cursor");
	$("div[class^='tt-dataset']").removeClass("tt-selectedDataSet");
	$(this).addClass("tt-selectedDataSet");
});
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
