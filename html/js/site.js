function P7_TMenu(b,og) { //v2.5 by Project Seven Development(PVII)
 var i,s,c,k,j,tN,hh;if(document.getElementById){
 if(b.parentNode && b.parentNode.childNodes){tN=b.parentNode.childNodes;}else{return;}
 for(i=0;i<tN.length;i++){if(tN[i].tagName=="DIV"){s=tN[i].style.display;
 hh=(s=="block")?"none":"block";if(og==1){hh="block";}tN[i].style.display=hh;}}
 c=b.firstChild;if(c.data){k=c.data;j=k.charAt(0);if(j=='+'){k='-'+k.substring(1,k.length);
 }else if(j=='-'){k='+'+k.substring(1,k.length);}c.data=k;}if(b.className=='p7plusmark'){
 b.className='p7minusmark';}else if(b.className=='p7minusmark'){b.className='p7plusmark';}}
}

function P7_setTMenu(b,og){ //v2.5 by Project Seven Development(PVII)
 if(og==9){return;}
 var i,d='',h='<style type=\"text/css\">';if(document.getElementById){
 var tA=navigator.userAgent.toLowerCase();if(window.opera){
 if(tA.indexOf("opera 5")>-1 || tA.indexOf("opera 6")>-1){return;}}
 for(i=1;i<20;i++){d+='div ';h+="\n#p7TMnav div "+d+"{display:none;}";}
 document.write(h+"\n</style>");}
}
P7_setTMenu();

function P7_TMopen(){ //v2.5 by Project Seven Development(PVII)
 var i,x,d,hr,ha,ef,a,ag;if(document.getElementById){d=document.getElementById('p7TMnav');
 if(d){hr=window.location.href;ha=d.getElementsByTagName("A");if(ha&&ha.length){
 for(i=0;i<ha.length;i++){if(ha[i].href){if(hr.indexOf(ha[i].href)>-1){
 /*ha[i].className="p7currentmark";a=ha[i].parentNode.parentNode;while(a){*/
 if(ha[i].onclick&&ha[i].onclick.toString().indexOf("P7_TMenu")>-1){a=ha[i].parentNode;
 }else{ha[i].className="p7currentmark";a=ha[i].parentNode.parentNode;}while(a){
 if(a.firstChild && a.firstChild.tagName=="A"){if(a.firstChild.onclick){
 ag=a.firstChild.onclick.toString();if(ag&&ag.indexOf("P7_TMenu")>-1){
 P7_TMenu(a.firstChild,1);}}}a=a.parentNode;}}}}}}}
 if (document.getElementById) {
   if (document.location.pathname != '/') {
	  document.getElementById("home").className='notp7currentmark';
  }}

}

function P7_TMall(a){ //v2.5 by Project Seven Development(PVII)
 var i,x,ha,s,tN;if(document.getElementById){ha=document.getElementsByTagName("A");
 for(i=0;i<ha.length;i++){if(ha[i].onclick){ag=ha[i].onclick.toString();
 if(ag&&ag.indexOf("P7_TMenu")>-1){if(ha[i].parentNode && ha[i].parentNode.childNodes){
 tN=ha[i].parentNode.childNodes;}else{break;}for(x=0;x<tN.length;x++){
 if(tN[x].tagName=="DIV"){s=tN[x].style.display;if(a==0&&s!='block'){P7_TMenu(ha[i]);
 }else if(a==1&&s=='block'){P7_TMenu(ha[i]);}break;}}}}}}
}

function P7_TMclass(){ //v2.5 by Project Seven Development(PVII)
 var i,x,d,tN,ag;if(document.getElementById){d=document.getElementById('p7TMnav');
 if(d){tN=d.getElementsByTagName("A");if(tN&&tN.length){for(i=0;i<tN.length;i++){
 ag=(tN[i].onclick)?tN[i].onclick.toString():false;if(ag&&ag.indexOf("P7_TMenu")>-1){
 tN[i].className='p7plusmark';}else{tN[i].className='p7defmark';}}}}}
}

function createCookie(name,value,days)
{
	if (days)
	{
		var date = new Date();
		date.setTime(date.getTime()+(days*24*60*60*1000));
		var expires = "; expires="+date.toGMTString();
	}
	else var expires = "";
	if (!readCookie(name)) {
		document.cookie = name+"="+value+expires+"; path=/";
	}
}

function createnewCookie(name,value,days)
{
	if (days)
	{
		var date = new Date();
		date.setTime(date.getTime()+(days*24*60*60*1000));
		var expires = "; expires="+date.toGMTString();
	}
	else var expires = "";
	document.cookie = name+"="+value+expires+"; path=/";
}

function readCookie(name)
{
	var nameEQ = name + "=";
	var ca = document.cookie.split(';');
	for(var i=0;i < ca.length;i++)
	{
		var c = ca[i];
		while (c.charAt(0)==' ') c = c.substring(1,c.length);
		if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
	}
	return null;
}

function eraseCookie(name)
{
	createCookie(name,"",-1);
}

rnd.today=new Date();
rnd.seed=rnd.today.getTime();

function rnd() {
    rnd.seed = (rnd.seed*9301+49297) % 233280;
    return rnd.seed/(233280.0);
};

function rand(number) {
    return Math.ceil(rnd()*number);
};

var refer=document.referrer;
createnewCookie('referer',refer,0);
doc=document.location;
createnewCookie('document',doc,0);
tid = new Date();
timeid = tid.getTime();
if (!readCookie('sessionid')) {
   createCookie('sessionid',timeid,0);
}
if (readCookie('userid')) {
   var myuserid = readCookie('userid');
   if (myuserid.length < 14) {
      eraseCookie('userid');
   }
}
if (readCookie('__utmv')) {
   var myutmv = readCookie('__utmv');
   if (myutmv.length < 24) {
      eraseCookie('__utmv');
   }
}
if (!readCookie('__utmv') && readCookie('userid')) {
var myuserid = readCookie('userid');
document.cookie = "__utmv=190262069."+myuserid+"; expires=Sun, 18 Jan 2038 00:00:00 GMT; path=/; domain=.oceannet.org;";
}
function P7_swapClass(){ //v1.4 by PVII
 alert('Called from site.js');
 var i,x,tB,j=0,tA=new Array(),arg=P7_swapClass.arguments;
 if(top.document.getElementsByTagName){for(i=4;i<arg.length;i++){tB=top.document.getElementsByTagName(arg[i]);
  for(x=0;x<tB.length;x++){tA[j]=tB[x];j++;}}for(i=0;i<tA.length;i++){
  if(tA[i].className){if(tA[i].id==arg[1]){if(arg[0]==1){
  tA[i].className=(tA[i].className==arg[3])?arg[2]:arg[3];}else{tA[i].className=arg[2];}
  }else if(arg[0]==1 && arg[1]=='none'){if(tA[i].className==arg[2] || tA[i].className==arg[3]){
  tA[i].className=(tA[i].className==arg[3])?arg[2]:arg[3];}
  }else if(tA[i].className==arg[2]){tA[i].className=arg[3];}}}}
}



