function bibcat_format_searchToolbar() {
	var sortOptions = $('.bfSortUl');
	$(".bfSortOptions").append(sortOptions);
	$(".bfSortOptions").hover(
						function(){$('.bfSortUl').show();},
						function(){$('.bfSortUl').hide();}
						);
	$('.bfSortUl').click(function(){$(this).hide()});
	var completeSortOptions = $(".bfSortOptions");
	$(".bf_searchToolbarUl").prepend(completeSortOptions);
	var resultSummary = $("#bibcat_resultSummary");
	$(".bf_searchToolbarUl").append(resultSummary);
	setFloatingHeader($('.bc_searchBox'))
};

function setFloatingHeader(hName) {
	var sectionSpacer = "<section class='headerSpacer' style='display:none'></section>";
	hName.after(sectionSpacer);
	$(window).scroll(function(){updateHeader(hName)});
};
function updateHeader(hName) {
	var sb = hName;
	var windowOffset = $(window).scrollTop();
	var sbH = sb.height();
	var sbTop = $("#bf_typeahead").offset().top;
	var logo = $('.appLogo');
	var logoTop = logo.offset().top;
	
	if (windowOffset >= logoTop) {
		logo.addClass("logoFloat");
		$('.appHeaderLogoSpacer').css('display','initial');
	} else {
		logo.removeClass("logoFloat");
		$('.appHeaderLogoSpacer').css('display','none');		
	}
	
	if ((windowOffset >= sbTop)) {
		if (windowOffset>=(sbH)) {
			sb.addClass("searchBoxFloat");
			$(".headerSpacer").css('height',sbH+"px").show();
		} else {
			sb.removeClass("searchBoxFloat");
			$(".headerSpacer").css('height',sbH+"px").hide();
		};
	} else {
		sb.removeClass("searchBoxFloat");
		$(".headerSpacer").css('height',sbH+"px").hide();
	};
};
		
