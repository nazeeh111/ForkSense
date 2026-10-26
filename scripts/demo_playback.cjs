#!/usr/bin/env node
/* Normal-speed local playback check. Uses an existing Playwright installation. */
'use strict';
const fs=require('node:fs');const path=require('node:path');const {pathToFileURL}=require('node:url');const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');const media=path.resolve(process.argv[2]||path.join(root,'docs/assets/demo.mp4'));
const receipt=path.resolve(process.argv[3]||path.join(root,'docs/assets/demo-source/playback-verification.json'));
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.FORKSENSE_CHROME||(process.platform==='darwin'?'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome':undefined)});try{
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));await page.goto(pathToFileURL(media).href);
 await page.locator('video').evaluate(async video=>{video.muted=true;video.playbackRate=1;await video.play()});
 await page.waitForFunction(()=>document.querySelector('video')?.ended,{},{timeout:35000});
 const result=await page.locator('video').evaluate(video=>{const q=video.getVideoPlaybackQuality();return {ended:video.ended,duration:video.duration,current_time:video.currentTime,playback_rate:video.playbackRate,width:video.videoWidth,height:video.videoHeight,total_frames:q.totalVideoFrames,dropped_frames:q.droppedVideoFrames,media_error:video.error?.message||null}});result.page_errors=errors;
 fs.writeFileSync(receipt,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
 if(!result.ended||result.media_error||errors.length)process.exitCode=1;
 }finally{await browser.close()}})().catch(error=>{console.error(error);process.exitCode=1});
