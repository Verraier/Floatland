// Loaded only from the private packaged copy. No remote debugging or sandbox flags.
const {app} = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const renderer = fs.readFileSync(path.join(__dirname, 'floatland-controls.js'), 'utf8');
app.on('browser-window-created', (_, win) => {
    const contents=win.webContents;
    function allowed() {
        if(contents.isDestroyed()) return false;
        try { return ['discord.com','canary.discord.com','ptb.discord.com'].includes(new URL(contents.getURL()).hostname); }
        catch { return false; }
    }
    async function update() {
        if(!allowed()) return;
        try {
            const settings=JSON.parse(fs.readFileSync(process.env.FLOATLAND_SETTINGS,'utf8'));
            const code='window.FloatlandSettings={read:async()=>('+JSON.stringify(settings)+')};\n'+renderer;
            const attached=await contents.executeJavaScript(code);
            if(!attached && !win.__floatlandWarned) {
                win.__floatlandWarned=true;
                console.warn('Floatland: Equibop controls not found yet. Enable its custom titlebar; original controls have been retained.');
            }
        } catch(error) { console.warn('Floatland Equibop adapter:',String(error)); }
    }
    contents.on('did-finish-load',update);
    const timer=setInterval(update,1000);
    win.on('closed',()=>clearInterval(timer));
});
require('./'+require('./floatland-entry.json'));
