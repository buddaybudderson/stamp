/* SITE behaviour, Oct 10, 2026. No library, no tracking, nothing sent anywhere.
   On every page: the header's groups and drawer, the day/night switch, a skip link target, reading progress
   and back to top. On standing pages also: breadcrumbs, "Cite this page", tables that become cards on a phone,
   live counts, "On this page", and the Docket and Chronicle charts moved to the top. */
(function(){
  var d=document, html=d.documentElement;
  function ready(f){ if(d.readyState!=="loading") f(); else d.addEventListener("DOMContentLoaded",f); }
  function el(tag,cls,inner){ var e=d.createElement(tag); if(cls) e.className=cls; if(inner!=null) e.innerHTML=inner; return e; }
  var MON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function house(t){ return MON[t.getMonth()]+" "+("0"+t.getDate()).slice(-2)+", "+t.getFullYear(); }

  ready(function(){
    var sh=d.querySelector(".sh"); if(!sh) return;
    d.body.classList.add("has-sh");

    // header groups
    var items=[].slice.call(sh.querySelectorAll(".sh-item"));
    function closeAll(except){ items.forEach(function(it){ if(it!==except){ it.classList.remove("open");
      var b=it.querySelector(".sh-x"); if(b) b.setAttribute("aria-expanded","false"); } }); }
    items.forEach(function(it){
      var b=it.querySelector(".sh-x"); if(!b) return;
      b.addEventListener("click",function(e){ e.preventDefault(); var o=!it.classList.contains("open");
        closeAll(it); it.classList.toggle("open",o); b.setAttribute("aria-expanded",o?"true":"false");
        if(o){ var f=it.querySelector(".sh-panel a"); if(f && e.detail===0) f.focus(); } });
      it.addEventListener("keydown",function(e){ if(e.key==="Escape"){ closeAll(); b.focus(); } });
    });
    d.addEventListener("click",function(e){ if(!e.target.closest(".sh-item")) closeAll(); });
    // drawer
    var mb=sh.querySelector(".sh-menu"), dr=d.querySelector(".sh-drawer");
    if(mb && dr){
      var toggle=function(){ var o=!dr.classList.contains("open"); dr.classList.toggle("open",o);
        html.classList.toggle("sh-lock",o); mb.setAttribute("aria-expanded",o?"true":"false");
        mb.querySelector(".lab").textContent=o?"Close":"Menu"; };
      mb.addEventListener("click",toggle);
      d.addEventListener("keydown",function(e){ if(e.key==="Escape" && dr.classList.contains("open")) toggle(); });
      dr.querySelectorAll("a,[data-pal]").forEach(function(a){ a.addEventListener("click",function(){ if(dr.classList.contains("open")) toggle(); }); });
    }
    // day / night: the same choice, and the same memory, as finish.js
    var mode=sh.querySelector(".sh-mode");
    if(mode){
      var paint=function(){ var n=html.getAttribute("data-mode")==="night"; mode.setAttribute("aria-pressed",n?"true":"false");
        mode.setAttribute("title",n?"Night: switch to day":"Day: switch to night"); };
      paint();
      mode.addEventListener("click",function(){ var n=html.getAttribute("data-mode")==="night"?"day":"night";
        try{ localStorage.setItem("stamp-mode",n); }catch(e){}
        html.setAttribute("data-mode",n); html.setAttribute("data-theme",n==="night"?"dark":"light"); paint(); });
    }
    // skip link target
    var main=d.getElementById("main")||d.querySelector("main")||d.querySelector(".wrap")||d.querySelector(".sx-issue")||d.querySelector("h1");
    if(main && !main.id) main.id="main";
    // reading progress and back to top, on pages long enough to need them
    var bar=el("div","sx-progress"); bar.setAttribute("aria-hidden","true"); d.body.appendChild(bar);
    var top=el("button","sx-top",'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg>');
    top.type="button"; top.setAttribute("aria-label","Back to top"); d.body.appendChild(top);
    top.addEventListener("click",function(){ window.scrollTo({top:0,behavior:"smooth"}); });
    var tick=function(){ var h=d.documentElement.scrollHeight-innerHeight, y=scrollY, long=h>innerHeight*1.5;
      bar.style.width=long?Math.min(100,y/h*100)+"%":"0"; top.classList.toggle("on",long && y>innerHeight); };
    addEventListener("scroll",tick,{passive:true}); addEventListener("resize",tick); tick();

    if(!d.body.classList.contains("rd") || d.body.classList.contains("rd-home")) return;

    // breadcrumbs: Home, the section, the page
    var cur=sh.querySelector('.sh-top[aria-current="true"]'), h1=d.querySelector(".wrap h1");
    if(h1){
      var c=el("nav","sx-crumbs"); c.setAttribute("aria-label","Breadcrumb");
      var parts=['<a href="/">Home</a>'];
      if(cur && cur.getAttribute("href")!==location.pathname) parts.push('<a href="'+cur.getAttribute("href")+'">'+cur.textContent+'</a>');
      parts.push('<span aria-current="page">'+h1.textContent.replace(/</g,"&lt;")+'</span>');
      c.innerHTML=parts.join('<i aria-hidden="true">/</i>'); h1.parentNode.insertBefore(c,h1); h1.style.marginTop="10px";
    }
    // cite this page, in the house form, with the date it was read
    var strap=d.querySelector(".wrap .strap");
    if(strap && h1){
      var canon=(d.querySelector('link[rel="canonical"]')||{}).href||location.href;
      var cb=el("button","sx-cite",'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg><span>Cite this page</span>');
      cb.type="button";
      cb.addEventListener("click",function(){
        var txt="Protocol STAMP, “"+h1.textContent.trim()+",” "+canon+", accessed "+house(new Date())+".";
        var done=function(){ cb.querySelector("span").textContent="Copied"; setTimeout(function(){ cb.querySelector("span").textContent="Cite this page"; },1800); };
        if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done,function(){ prompt("Copy this citation:",txt); });
        else prompt("Copy this citation:",txt);
      });
      strap.appendChild(cb);
    }
    // the Docket's and the Chronicle's charts go first, under the title
    var viz=d.querySelector("figure.dk-viz"), vstrap=d.querySelector(".wrap .strap");
    if(viz && vstrap){ vstrap.insertAdjacentElement("afterend",viz); viz.style.marginTop="22px"; }

    // tables become cards on a phone
    d.querySelectorAll("table").forEach(function(t){
      var heads=[].map.call(t.querySelectorAll("tr:first-child th"),function(th){return th.textContent.trim();});
      if(!heads.length) return;
      t.classList.add("stacked");
      var w=t.parentElement; if(w && w.classList.contains("tablescroll")) w.classList.add("stack");
      t.querySelectorAll("tr").forEach(function(tr){ [].forEach.call(tr.children,function(td,i){
        if(td.tagName==="TD" && heads[i]) td.setAttribute("data-label",heads[i]); }); });
    });

    // live counts: a tile that counts rows cannot drift from them
    d.querySelectorAll("[data-count]").forEach(function(e){ e.textContent=d.querySelectorAll(e.getAttribute("data-count")).length; });
    d.querySelectorAll("[data-next]").forEach(function(e){ var n=d.querySelector(e.getAttribute("data-next"));
      e.textContent=n?n.textContent.trim():"Nothing due"; });
    var rows=[].slice.call(d.querySelectorAll("#register table tr")).filter(function(tr){return tr.children[1] && tr.children[1].tagName==="TD";});
    if(rows.length){
      d.querySelectorAll("[data-count-kind]").forEach(function(e){ var k=e.getAttribute("data-count-kind");
        e.textContent=rows.filter(function(tr){return tr.children[1].textContent.trim()===k;}).length; });
      d.querySelectorAll("[data-count-first]").forEach(function(e){ e.textContent=rows[rows.length-1].children[0].textContent.trim(); });
    }

    // on this page
    var secs=[].filter.call(d.querySelectorAll(".wrap section"),function(s){ return s.querySelector("h2"); });
    if(secs.length<3) return;
    var used={};
    var links=secs.map(function(s){
      var h=s.querySelector("h2"), e=s.querySelector(".eyebrow");
      if(!s.id){ var id=(e?e.textContent:h.textContent).toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"").slice(0,40)||"s";
        while(used[id]||d.getElementById(id)) id+="-2"; s.id=id; }
      used[s.id]=1;
      return {id:s.id, t:(e && e.textContent.trim().length<34 ? e.textContent : h.textContent).trim()};
    });
    function mk(cls,title){ var n=d.createElement("nav"); n.className=cls; n.setAttribute("aria-label","On this page");
      n.innerHTML=(title?'<p>On this page</p>':"")+links.map(function(l){return '<a href="#'+l.id+'">'+l.t.replace(/</g,"&lt;")+'</a>';}).join("");
      return n; }
    var rail=mk("otp",true), col=el("div","otp-col"), wrapEl=d.querySelector(".wrap"); col.appendChild(rail); (wrapEl||d.body).appendChild(col); d.body.classList.add("has-otp");
    var chips=mk("otp-chips",false), anchor=d.querySelector(".wrap .lede")||d.querySelector(".wrap .strap");
    if(anchor) anchor.insertAdjacentElement("afterend",chips);
    if("IntersectionObserver" in window){
      var as=rail.querySelectorAll("a");
      var io=new IntersectionObserver(function(es){ es.forEach(function(en){ if(en.isIntersecting){
        as.forEach(function(a){ a.classList.toggle("on",a.getAttribute("href")==="#"+en.target.id); }); } }); },
        {rootMargin:"-30% 0px -60% 0px"});
      secs.forEach(function(s){ io.observe(s); });
    }
  });
})();
