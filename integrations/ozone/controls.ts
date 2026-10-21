export {};
// Installed only in an isolated Equibop source copy. Keep its existing IPC bridge.
const paths = ["M4 4L10 10M10 4L4 10", "M3 7H11", "M4 4H10V10H4Z"];
const actions = ["close", "minimize", "maximize"] as const;
let settings: Record<string, any> = {};
const css = document.createElement("style");
css.textContent = `
.floatland-controls { display:flex; align-items:center; gap:var(--fl-gap,10px); padding:0 12px; -webkit-app-region:no-drag; }
.floatland-controls button { width:var(--fl-size,14px);height:var(--fl-size,14px);min-width:0;padding:0;border-radius:50%;border:1px solid #ffffff38;display:grid;place-items:center;cursor:default; }
.floatland-controls button:active { filter:brightness(1.2); }
.floatland-controls svg {width:100%;height:100%;opacity:0;pointer-events:none;}
.floatland-controls:hover svg,.floatland-controls:focus-within svg {opacity:1;}
`;
document.documentElement.appendChild(css);
function style(box: HTMLElement) {
    const size = Math.max(8, Math.min(20, Number(settings.button_size) || 14));
    box.style.setProperty("--fl-size", `${size}px`);
    box.style.setProperty("--fl-gap", `${Math.max(0,Math.min(40,Number(settings.button_spacing) || 0))}px`);
    const requested=typeof settings.buttons_order==="string"?settings.buttons_order.split(","):actions.slice();
    const order=settings.buttons_side==="left"?requested.slice().reverse():requested;
    const original=document.querySelector<HTMLElement>('[class*="winButtons_"]');
    if(original?.parentElement && box.parentElement) {
        const parent=original.parentElement;
        if(settings.buttons_side==="left" && parent.firstElementChild!==box) parent.prepend(box);
        else if(settings.buttons_side!=="left" && box.nextElementSibling!==original) original.before(box);
    }
    for (const button of box.querySelectorAll<HTMLButtonElement>("button")) {
        const i=Number(button.dataset.index);
        const fallback=["#f55c57","#fabe2e","#33c459"][i];
        const candidate=settings[actions[i]+"_color"];
        const color=/^#[0-9a-f]{6}$/i.test(candidate)?candidate:fallback;
        button.style.background=color;
        button.style.display=order.includes(actions[i])?"grid":"none";
        button.style.order=String(order.indexOf(actions[i]));
        const svg=button.querySelector("svg");
        if(svg) svg.style.opacity=settings.button_icons===false?"0":settings.button_hover_only===false?"1":"";
    }
}
function install() {
    // Refuse to hide anything unless the application's own control group exists.
    const original=document.querySelector<HTMLElement>('[class*="winButtons_"]');
    if(!original || !original.parentElement || document.getElementById("floatland-controls")) return;
    const box=document.createElement("div"); box.id="floatland-controls"; box.className="floatland-controls";
    actions.forEach((action,i)=>{
        const button=document.createElement("button"); button.type="button"; button.dataset.index=String(i);
        button.title=action; button.setAttribute("aria-label",action);
        button.innerHTML=`<svg viewBox="0 0 14 14" aria-hidden="true"><path d="${paths[i]}" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>`;
        button.style.color="#281a1688";
        button.onclick=()=>VesktopNative.win[action]();
        box.appendChild(button);
    });
    style(box); original.before(box); original.style.display="none";
}
let queued=false;
new MutationObserver(()=>{if(!queued){queued=true;queueMicrotask(()=>{queued=false;install();});}}).observe(document.documentElement,{childList:true,subtree:true});
async function update() {
    try { settings=await (window as any).FloatlandSettings.read(); }
    catch { return; }
    install(); document.querySelectorAll<HTMLElement>(".floatland-controls").forEach(style);
}
void update(); setInterval(update,1000);
