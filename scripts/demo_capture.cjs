#!/usr/bin/env node
/* Capture the real, sanitized run report. No synthetic agent events or UI values.
 * Requires existing Playwright and Chrome/Chromium. No runtime downloads.
 * Native screencast frames retain Chrome timestamps; encode separately with FFmpeg.
 * NODE_PATH may point to an existing Playwright installation.
 * Run: node scripts/demo_capture.cjs [fresh-output-directory]
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');
const root = path.resolve(__dirname,'..');
const report = path.resolve(process.env.FORKSENSE_REPORT || path.join(root,'docs/evidence/live-codex-demo/report.html'));
const jsonPath = path.join(root,'docs/evidence/live-codex-demo/report.json');
const data = JSON.parse(fs.readFileSync(jsonPath,'utf8'));
const output = path.resolve(process.argv[2] || path.join(root,'artifacts','demo-'+new Date().toISOString().replace(/[:.]/g,'-')));
if(fs.existsSync(output)) throw new Error('Output must be a fresh directory: '+output);
fs.mkdirSync(output,{recursive:true});
const sha = p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const delay = ms=>new Promise(resolve=>setTimeout(resolve,ms));
const source = {report:'docs/evidence/live-codex-demo/report.html',report_sha256:sha(report),json_sha256:sha(jsonPath),patch_sha256:sha(path.join(path.dirname(jsonPath),data.selected.patch_path)),task:data.task,status:data.status,recorded_run_duration_seconds:data.totals.duration};
const log=[];let ownedBrowser;
(async()=>{
 const executablePath=process.env.FORKSENSE_CHROME || (process.platform==='darwin'?'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome':undefined);
 const browser = ownedBrowser = await chromium.launch({headless:true,...(executablePath?{executablePath}:{} )});
 const screenshots=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1});
 const page=await screenshots.newPage();
 const pageErrors=[];page.on('pageerror',e=>pageErrors.push(String(e)));
 await page.goto(pathToFileURL(report).href);await page.evaluate(()=>document.fonts.ready);
 await page.screenshot({path:path.join(output,'report-desktop.png'),fullPage:true});
 const desktopOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 const forkMap=await page.evaluate(()=>({nodes:document.querySelectorAll('.fork-node').length,base_children:document.querySelectorAll('.fork-branches > .fork-branch').length,verification_children:document.querySelectorAll('.fork-verification').length}));
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'report-mobile.png'),fullPage:true});
 const mobileOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 await screenshots.close();
 const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1,});
 const capture=await context.newPage();capture.on('pageerror',e=>pageErrors.push(String(e)));
 await capture.goto(pathToFileURL(report).href);await capture.evaluate(()=>document.fonts.ready);
 const cdp=await context.newCDPSession(capture);
 const frames=[];const framesDir=path.join(output,'native-frames');fs.mkdirSync(framesDir);
 const recordingStart=Date.now();
 cdp.on('Page.screencastFrame',event=>{
   const filename='frame-'+String(frames.length).padStart(5,'0')+'.jpg';
   fs.writeFileSync(path.join(framesDir,filename),Buffer.from(event.data,'base64'));
   frames.push({file:'native-frames/'+filename,timestamp:event.metadata.timestamp,received_ms:Date.now()-recordingStart});
   cdp.send('Page.screencastFrameAck',{sessionId:event.sessionId}).catch(()=>{});
 });
 await cdp.send('Page.startScreencast',{format:'jpeg',quality:95,maxWidth:1440,maxHeight:900,everyNthFrame:1});
 const firstReady=Date.now();
 async function mark(label){log.push({label,elapsed_ms:Date.now()-firstReady});}
 async function scrollTo(locator){await locator.evaluate(el=>window.scrollTo({top:window.scrollY+el.getBoundingClientRect().top-35,behavior:'smooth'}));await delay(650);}
 await mark('Report loaded; actual recorded totals visible');await delay(2500);
 await scrollTo(capture.locator('.fork-map'));await mark('Actual frozen-base worktree forks visible');await delay(1800);
 const probe=capture.locator('.step[data-kind="probe"]');await capture.locator('[data-fork-target="evidence-step-0"]').click();await probe.getByText('Experiment stderr',{exact:true}).click();await scrollTo(probe);await mark('Probe stderr opened; observed assertion failure visible');await delay(4500);
 const repair=capture.locator('.step[data-kind="repair"]');await repair.locator('.step-detail > summary').click();await repair.getByText('Verifier stderr',{exact:true}).click();await scrollTo(repair);await mark('Repair and independent verifier opened; four contract tests visible');await delay(4000);
 const patch=repair.getByText('Source patch',{exact:true});if(await patch.count()){await patch.click();await scrollTo(patch);await mark('Exact source patch opened');await delay(2000);}
 await scrollTo(capture.locator('.selection'));await mark('Selected patch identity and verification visible');await delay(5200);
 const duration=Date.now()-firstReady;
 await cdp.send('Page.stopScreencast');await delay(100);await context.close();await browser.close();
 if(!frames.length)throw new Error('Chrome returned no native screencast frames');
 const lines=['ffconcat version 1.0'];
 frames.forEach((frame,i)=>{const next=frames[i+1];const seconds=next?Math.max(.001,next.timestamp-frame.timestamp):Math.max(.001,(duration-frame.received_ms)/1000);lines.push("file '"+frame.file+"'",'duration '+seconds.toFixed(6));frame.sha256=sha(path.join(output,frame.file));});
 lines.push("file '"+frames[frames.length-1].file+"'");
 fs.writeFileSync(path.join(output,'frames.ffconcat'),lines.join('\n')+'\n');
 const manifest={schema_version:1,description:'Recorded report walkthrough of a live Codex run. This is not real-time agent footage.',source,viewport:{width:1440,height:900},audio:false,native_capture_elapsed_ms:duration,frame_capture:'Native Chrome screencast frames; original timestamps; sample-and-hold between frames.',frames,actions:log,checks:{page_errors:pageErrors,desktop_overflow:desktopOverflow,mobile_overflow:mobileOverflow,fork_map:forkMap},files:{desktop_sha256:sha(path.join(output,'report-desktop.png')),mobile_sha256:sha(path.join(output,'report-mobile.png')),frame_concat_sha256:sha(path.join(output,'frames.ffconcat'))}};
 fs.writeFileSync(path.join(output,'capture-manifest.json'),JSON.stringify(manifest,null,2)+'\n');console.log(JSON.stringify({output,source,actions:log,checks:manifest.checks,frames:frames.length,duration_ms:duration},null,2));
 if(pageErrors.length||desktopOverflow||mobileOverflow)process.exitCode=1;
})().catch(async error=>{console.error(error);if(ownedBrowser)await ownedBrowser.close();process.exitCode=1});
