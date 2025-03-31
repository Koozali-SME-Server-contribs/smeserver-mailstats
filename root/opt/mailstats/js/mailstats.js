window.onload = function(){doNavs();} 
//function openTab(event, tabId){
//// Get all elements with class="tab-content" and hide them
//const tabContents = document.querySelectorAll('.tab-content');
//tabContents.forEach(content => content.classList.remove('tab-content-active'));

//// Get all elements with class="tab" and remove the class "tab-active"
//const tabs = document.querySelectorAll('.tab');
//tabs.forEach(tab => tab.classList.remove('tab-active'));

//// Show the current tab content, and add an "active" class to the clicked tab
//document.getElementById(tabId).classList.add('tab-content-active');
//event.target.classList.add('tab-active');}

function LinkCheck(url){
	var http = new XMLHttpRequest();
	http.open('HEAD', url, false);
	http.send();
	return http.status!=404;
}
function doNavs() {
	var aTags = document.getElementsByTagName('a'),
		atl = aTags.length,i;
	for (i = 0; i < atl; i++) {
		if (aTags[i].innerText == "Previous") {
			if (!LinkCheck(aTags[i].href)) { 
				aTags[i].style.visibility = "hidden";
			} else {
				aTags[i].style.visibility = "visible";
			}
		} else if (aTags[i].innerText == "Next") {
			if (!LinkCheck(aTags[i].href)) { 
				aTags[i].style.visibility = "hidden";
			} else {
				aTags[i].style.visibility = "visible";
			}
		}
	}
}

function openTab(evt, tabName) {
// Declare all variables
var i, tab_content, tab;

// Get all elements with class="tab_content" and hide them
tab_content = document.getElementsByClassName("tab-content");
for (i = 0; i < tab_content.length; i++) {
tab_content[i].style.display = "none";
}

// Get all elements with class="tab" and remove the class "active"
tab = document.getElementsByClassName("tab");
for (i = 0; i < tab.length; i++) {
tab[i].className = tab[i].className.replace(" tab-active", "");
}

// Show the current tab, and add an "active" class to the link that opened the tab
document.getElementById(tabName).style.display = "block";
evt.currentTarget.className += " tab-active";

// Store the active tab index
sessionStorage.setItem('activeTab', evt.currentTarget.getAttribute("data-index"));
}

document.addEventListener("DOMContentLoaded", function() {
    // Attach click event handler for all divs with the class "tab"
    document.querySelectorAll(".tab").forEach(function(tab) {
        tab.addEventListener("click", function(event) {
            // Get the data-index attribute value
            const tabIndex = this.getAttribute("data-index");

            // Dynamically call openTab with the correct tab parameter
            openTab(event, `tab${tabIndex}`);
        });
    });
});