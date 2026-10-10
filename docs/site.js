/* SITE v3 behaviour, Oct 09, 2026. No library, no tracking, nothing sent anywhere.
   1. The header: open a group on click or keyboard, close on Escape or a click elsewhere;
      the drawer for phones and tablets.
   2. Tables on standing pages: each cell learns its column name, so a phone can show a row as a card.
   3. "On this page": built from the page's own sections, a rail on wide screens, chips on narrow ones. */
(function(){
  var d=document, html=d.documentElement;
  function ready(f){ if(d.readyState!=="loading") f(); else d.addEventListener("DOMContentLoaded",f); }
  ready(function(){
    var sh=d.querySelector(".sh"); if(!sh) return;
    d.body.classList.add("has-sh");

    // 1. header groups
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
    // the drawer
    var mb=sh.querySelector(".sh-menu"), dr=d.querySelector(".sh-drawer");
    if(mb && dr){
      mb.addEventListener("click",function(){ var o=!dr.classList.contains("open"); dr.classList.toggle("open",o);
        html.classList.toggle("sh-lock",o); mb.setAttribute("aria-expanded",o?"true":"false");
        mb.querySelector(".lab").textContent=o?"Close":"Menu"; });
      d.addEventListener("keydown",function(e){ if(e.key==="Escape" && dr.classList.contains("open")) mb.click(); });
      dr.querySelectorAll("a").forEach(function(a){ a.addEventListener("click",function(){ if(dr.classList.contains("open")) mb.click(); }); });
    }
    // the drawer's search opens the same page search as the header
    dr && dr.querySelectorAll("[data-pal]").forEach(function(b){ b.addEventListener("click",function(){ if(dr.classList.contains("open")) mb.click(); }); });

    if(!d.body.classList.contains("rd") || d.body.classList.contains("rd-home")) return;

    // 2. tables become cards on a phone
    d.querySelectorAll("table").forEach(function(t){
      var heads=[].map.call(t.querySelectorAll("tr:first-child th"),function(th){return th.textContent.trim();});
      if(!heads.length) return;
      t.classList.add("stacked");
      var w=t.parentElement; if(w && w.classList.contains("tablescroll")) w.classList.add("stack");
      t.querySelectorAll("tr").forEach(function(tr){ [].forEach.call(tr.children,function(td,i){
        if(td.tagName==="TD" && heads[i]) td.setAttribute("data-label",heads[i]); }); });
    });

    // live counts on the register: the tiles count the rows, so they cannot drift from them
    var rows=[].slice.call(d.querySelectorAll("#register table tr")).filter(function(tr){return tr.children[1] && tr.children[1].tagName==="TD";});
    if(rows.length){
      d.querySelectorAll("[data-count-kind]").forEach(function(el){ var k=el.getAttribute("data-count-kind");
        el.textContent=rows.filter(function(tr){return tr.children[1].textContent.trim()===k;}).length; });
      d.querySelectorAll("[data-count-first]").forEach(function(el){ el.textContent=rows[rows.length-1].children[0].textContent.trim(); });
    }

    // 3. on this page
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
    var rail=mk("otp",true); d.body.appendChild(rail); d.body.classList.add("has-otp");
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
