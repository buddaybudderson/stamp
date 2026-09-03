/* THE FINISH IS THE DAY, AND THE DAY IS CHICAGO'S. Runs in <head>, before first
   paint, so the page never flashes the wrong color. A page may pin its finish with
   <html data-pin="sun">: an issue wears the day it was issued, not the day it is read.
   The switch sets data-mode (day/night) AND data-theme (light/dark): the frozen issue
   pages read data-theme, everything else reads data-mode. The choice is remembered. */
(function(){
  var FIN={Mon:"moon",Tue:"mars",Wed:"mercury",Thu:"jupiter",Fri:"venus",Sat:"saturn",Sun:"sun"};
  var r=document.documentElement, d="Sat";
  try{ d=new Intl.DateTimeFormat("en-US",{timeZone:"America/Chicago",weekday:"short"}).format(new Date()); }catch(e){}
  r.setAttribute("data-day",d);
  r.setAttribute("data-finish", r.getAttribute("data-pin") || FIN[d] || "saturn");
  var m=null; try{ m=localStorage.getItem("stamp-mode"); }catch(e){}
  if(!m){ m=(window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches)?"night":"day"; }
  apply(m);
  function apply(mode){
    r.setAttribute("data-mode",mode);
    r.setAttribute("data-theme",mode==="night"?"dark":"light");
    var b=document.getElementById("modeswitch"); if(b){ b.querySelector(".lab").textContent=(mode==="night"?"Night":"Day");
      b.setAttribute("aria-pressed",mode==="night"?"true":"false"); }
  }
  window.addEventListener("DOMContentLoaded",function(){
    var fin=r.getAttribute("data-finish"), pinned=!!r.getAttribute("data-pin");
    var b=document.createElement("button"); b.id="modeswitch"; b.className="modeswitch"; b.type="button";
    b.setAttribute("aria-label","Switch between day and night");
    b.innerHTML='<span class="dot" aria-hidden="true"></span><span class="lab"></span><span class="fin">\u00b7 '+
      (pinned?"issued under ":"")+fin.charAt(0).toUpperCase()+fin.slice(1)+'</span>';
    b.addEventListener("click",function(){ var n=r.getAttribute("data-mode")==="night"?"day":"night";
      try{ localStorage.setItem("stamp-mode",n); }catch(e){} apply(n); });
    document.body.appendChild(b); apply(r.getAttribute("data-mode"));
    // The playground pill: sits left of the switch, sends a first-time reader to the one page
    // where the day may be changed. Not shown on the Colophon, which is that page.
    if(location.pathname.indexOf("/colophon")!==0){
      var a=document.createElement("a"); a.className="playlink"; a.href="/colophon/#playground";
      a.setAttribute("aria-label","Playground: see all seven finishes");
      a.innerHTML='<span class="seven" aria-hidden="true">'+["#E4EDF6","#F4E3E3","#E4EDE3","#EBE3F5","#F7E7D8","#E6E9ED","#F8EED3"].map(function(c){return '<i style="background:'+c+'"></i>'}).join("")+'</span><span class="txt">Playground</span>';
      document.body.appendChild(a);
      // place the switch to the left of the pill once both are laid out
      requestAnimationFrame(function(){ b.style.right=(a.offsetWidth+22)+"px"; });
    }
  });
})();

/* ADVERTISING. One slot, home page and The Bench essays only, never on an issue.
   Empty string = nothing loads, the slot stays hidden, no Google code on the page.
   Fill in after AdSense approval: ADS_CLIENT="ca-pub-XXXXXXXXXXXXXXXX". The loader
   runs only on pages that contain a slot, so issue pages cannot pick it up by accident. */
var ADS_CLIENT = "";
(function(){
  if(!ADS_CLIENT) return;
  window.addEventListener("DOMContentLoaded",function(){
    var ins=document.querySelector("ins.adsbygoogle"); if(!ins) return;
    if(location.pathname.indexOf("/calibration/")===0||location.pathname.indexOf("/log/")===0) return;
    ins.setAttribute("data-ad-client",ADS_CLIENT);
    document.documentElement.setAttribute("data-ads","on");
    var s=document.createElement("script"); s.async=true; s.crossOrigin="anonymous";
    s.src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client="+ADS_CLIENT;
    document.head.appendChild(s);
    s.onload=function(){ (window.adsbygoogle=window.adsbygoogle||[]).push({}); };
  });
})();
