/* Wonderland · Hermes-on-Android Docs shell — injects chrome, builds TOC,
   wires interactions. Structurally identical to the Mazemaker docs shell, so
   the two sites feel like one family. Each page sets
   <body data-tab="..." data-page="..."> and provides only <main class="content">. */
(function(){
  "use strict";
  var BASE = "/";

  var TABS = [
    ["Home", BASE, "home"],
    ["Get started", BASE+"getting-started/", "getting-started"],
    ["The pod", BASE+"pod/", "pod"],
    ["Gateway", BASE+"gateway/", "gateway"],
    ["Podroid VM", BASE+"podroid/", "podroid"],
    ["Apps", BASE+"apps/", "apps"],
    ["Pairing", BASE+"pairing/", "pairing"],
    ["Help", BASE+"troubleshooting/", "troubleshooting"]
  ];

  var NAV = [
    ["Start here", [
      ["Overview", BASE],
      ["The architecture", BASE+"#picture"],
      ["Prerequisites", BASE+"getting-started/"],
      ["Build order", BASE+"getting-started/#order"]
    ]],
    ["On the desktop", [
      ["The memory pod", BASE+"pod/"],
      ["Secrets & license", BASE+"pod/#secrets"],
      ["The PRO gateway", BASE+"gateway/"],
      ["Pairing code", BASE+"gateway/#pairing"]
    ]],
    ["On the phone", [
      ["Podroid — the Linux VM", BASE+"podroid/"],
      ["Build the rootfs", BASE+"podroid/#rootfs"],
      ["hermes-agent & the key", BASE+"podroid/#hermes"],
      ["The three apps", BASE+"apps/"]
    ]],
    ["Go live", [
      ["Pairing & wiring", BASE+"pairing/"],
      ["End-to-end verify", BASE+"pairing/#verify"],
      ["Deploy the website", BASE+"pairing/#deploy"]
    ]],
    ["Help", [
      ["Troubleshooting", BASE+"troubleshooting/"],
      ["Security model", BASE+"troubleshooting/#security"]
    ]]
  ];

  var ICON = {
    search:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>',
    moon:'<svg id="iconMoon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>',
    sun:'<svg id="iconSun" style="display:none" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M19.1 4.9l-1.8 1.8M6.7 17.3l-1.8 1.8"/></svg>',
    gh:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2A10 10 0 0 0 8.8 21.5c.5.1.7-.2.7-.5v-1.7c-2.8.6-3.4-1.4-3.4-1.4-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8.1-.6.3-1.1.6-1.3-2.2-.3-4.5-1.1-4.5-4.9a3.8 3.8 0 0 1 1-2.7 3.6 3.6 0 0 1 .1-2.6s.8-.3 2.7 1a9.3 9.3 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .5 1.4.2 2.4.1 2.6a3.8 3.8 0 0 1 1 2.7c0 3.8-2.3 4.6-4.5 4.9.3.3.7.9.7 1.8v2.7c0 .3.2.6.7.5A10 10 0 0 0 12 2Z"/></svg>',
    burger:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M3 12h18M3 18h18"/></svg>',
    list:'<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>'
  };

  var page = document.body.dataset.page || "home";
  var tab  = document.body.dataset.tab  || page;

  function slug(t){return t.toLowerCase().replace(/[^\w]+/g,"-").replace(/^-|-$/g,"");}
  function samePath(href){
    try{var u=new URL(href, location.origin);return u.pathname===location.pathname && !u.hash;}catch(e){return false;}
  }

  /* ---- header ---- */
  var hdr=document.createElement("header"); hdr.className="hdr";
  hdr.innerHTML=
    '<div class="hdr-inner">'+
      '<button class="burger" aria-label="Menu">'+ICON.burger+'</button>'+
      '<a class="brand" href="'+BASE+'"><span class="dot"></span> wonderland <small>hermes · android</small></a>'+
      '<div class="hdr-spacer"></div>'+
      '<label class="search">'+ICON.search+'<input id="docSearch" type="text" placeholder="Search the docs" aria-label="Search"><kbd>/</kbd></label>'+
      '<div class="hdr-icons">'+
        '<button class="icon-btn" id="themeBtn" title="Switch theme">'+ICON.moon+ICON.sun+'</button>'+
        '<a class="gh" href="https://github.com/itsXactlY/Jackrabbit-wonderland" target="_blank" rel="noopener">'+ICON.gh+'<span>GitHub</span></a>'+
      '</div>'+
    '</div>';

  /* ---- tabs ---- */
  var tabs=document.createElement("nav"); tabs.className="tabs"; tabs.setAttribute("aria-label","Sections");
  var ti='<div class="tabs-inner">';
  TABS.forEach(function(t){
    ti+='<a class="tab'+(t[2]===tab?' active':'')+'" href="'+t[1]+'">'+t[0]+'</a>';
  });
  ti+='</div>'; tabs.innerHTML=ti;

  /* ---- sidebar ---- */
  var side=document.createElement("nav"); side.className="side"; side.setAttribute("aria-label","Page navigation");
  var sh="";
  NAV.forEach(function(g){
    sh+='<div class="side-group"><div class="gtitle">'+g[0]+'</div>';
    g[1].forEach(function(it){
      var active=samePath(it[1]);
      sh+='<a href="'+it[1]+'"'+(active?' class="active" aria-current="page"':'')+'>'+it[0]+'</a>';
    });
    sh+='</div>';
  });
  side.innerHTML=sh;

  /* ---- mount ---- */
  var content=document.querySelector("main.content");
  var shell=document.createElement("div"); shell.className="shell";
  var scrim=document.createElement("div"); scrim.className="scrim";

  document.body.insertBefore(tabs, content);
  document.body.insertBefore(hdr, tabs);
  document.body.insertBefore(scrim, content);

  var toc=document.createElement("aside"); toc.className="toc"; toc.setAttribute("aria-label","On this page");
  var heads=content.querySelectorAll("h2, h3");
  var th='<div class="toc-title">'+ICON.list+'On this page</div>';
  heads.forEach(function(h){
    if(!h.id) h.id=slug(h.textContent);
    if(!h.querySelector(".anchor")){
      var a=document.createElement("a"); a.className="anchor"; a.href="#"+h.id; a.textContent="¶"; h.appendChild(a);
    }
    th+='<a class="'+(h.tagName==="H3"?"sub":"")+'" href="#'+h.id+'">'+h.firstChild.textContent.trim()+'</a>';
  });
  toc.innerHTML=th;

  content.parentNode.insertBefore(shell, content);
  shell.appendChild(side); shell.appendChild(content); shell.appendChild(toc);

  /* ---- footer ---- */
  var foot=document.createElement("footer"); foot.className="docfoot";
  foot.innerHTML='<span>© 2026 · Hermes on Android · <strong>part of the wonderland family</strong></span>'+
    '<span>Sibling: <a href="https://mazemaker.online/docs/" target="_blank" rel="noopener">Mazemaker docs</a> · <a href="https://github.com/itsXactlY/Jackrabbit-wonderland" target="_blank" rel="noopener">Jackrabbit-wonderland</a></span>';
  document.body.appendChild(foot);

  /* ---- theme ---- */
  var root=document.documentElement, tb=document.getElementById("themeBtn");
  var moon=document.getElementById("iconMoon"), sun=document.getElementById("iconSun");
  function apply(t){root.setAttribute("data-theme",t);try{localStorage.setItem("wl-docs-theme",t);}catch(e){}
    moon.style.display=t==="dark"?"":"none"; sun.style.display=t==="dark"?"none":"";}
  try{var saved=localStorage.getItem("wl-docs-theme"); if(saved) apply(saved); else apply(root.getAttribute("data-theme")||"dark");}catch(e){apply("dark");}
  tb.addEventListener("click",function(){apply(root.getAttribute("data-theme")==="dark"?"light":"dark");});

  /* ---- content tabs ---- */
  document.querySelectorAll("[data-ctabs]").forEach(function(grp){
    var btns=grp.querySelectorAll(".ctab-btn"), pans=grp.querySelectorAll(".ctab-panel");
    btns.forEach(function(b,i){b.addEventListener("click",function(){
      btns.forEach(function(x){x.classList.remove("active");}); pans.forEach(function(x){x.classList.remove("active");});
      b.classList.add("active"); if(pans[i])pans[i].classList.add("active");});});
  });

  /* ---- copy ---- */
  document.querySelectorAll(".copy").forEach(function(b){
    b.addEventListener("click",function(){
      var pre=b.closest(".code").querySelector(".code-body");
      navigator.clipboard.writeText(pre.textContent.trim()).then(function(){
        var old=b.innerHTML; b.classList.add("ok"); b.innerHTML="✓ Copied";
        setTimeout(function(){b.classList.remove("ok"); b.innerHTML=old;},1400);
      });
    });
  });

  /* ---- mobile drawer ---- */
  var burger=document.querySelector(".burger");
  function closeNav(){document.body.classList.remove("nav-open");}
  burger.addEventListener("click",function(){document.body.classList.toggle("nav-open");});
  scrim.addEventListener("click",closeNav);
  side.querySelectorAll("a").forEach(function(a){a.addEventListener("click",closeNav);});

  /* ---- scrollspy ---- */
  var links=[].slice.call(toc.querySelectorAll("a:not(.toc-title)"));
  var anchors=links.map(function(a){return document.getElementById(a.getAttribute("href").slice(1));});
  function spy(){
    var i=-1;
    for(var j=0;j<anchors.length;j++){if(anchors[j]&&anchors[j].getBoundingClientRect().top<150)i=j;}
    links.forEach(function(x){x.classList.remove("active");});
    if(i>=0&&links[i])links[i].classList.add("active");
  }
  document.addEventListener("scroll",spy,{passive:true}); spy();

  /* ---- search (sidebar filter) ---- */
  var search=document.getElementById("docSearch");
  search.addEventListener("input",function(){
    var q=search.value.trim().toLowerCase();
    side.querySelectorAll(".side-group").forEach(function(g){
      var any=false;
      g.querySelectorAll("a").forEach(function(a){
        var hit=!q||a.textContent.toLowerCase().indexOf(q)>-1;
        a.style.display=hit?"":"none"; if(hit)any=true;
      });
      g.style.display=any?"":"none";
    });
  });
  document.addEventListener("keydown",function(e){
    if(e.key==="/"&&document.activeElement.tagName!=="INPUT"){e.preventDefault();search.focus();}
    if(e.key==="Escape"){closeNav();}
  });
})();
