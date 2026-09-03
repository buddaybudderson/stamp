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
  });
})();
