'use strict';
const SOURCE = 'j2rk8ycXe3c';
const events = [];
const signals = document.getElementById('signals');
const statusText = document.getElementById('status');
let player;
let timer;
let hasStopped = false;
function log(kind, detail) {
  events.push({at:new Date().toISOString(),kind,detail});
  render();
}
function render() {
  let live = {};
  try {
    if (player && typeof player.getCurrentTime === 'function') {
      live = {
        sourceUrl:player.getVideoUrl(),
        currentTime:player.getCurrentTime(),
        duration:player.getDuration(),
        state:player.getPlayerState(),
        quality:player.getPlaybackQuality(),
        muted:player.isMuted(),
        volume:player.getVolume()
      };
    }
  } catch (error) { live = {inspectionError:String(error)}; }
  signals.textContent=JSON.stringify({
    observedAt:new Date().toISOString(),
    pageOrigin:location.origin,
    sourceId:SOURCE,
    window:[0,40],
    nativeAudioVerified:false,
    nativeFramesVerified:false,
    productionApproved:false,
    live,
    events
  },null,2);
  if (live.currentTime >= 40 && !hasStopped) {
    hasStopped = true;
    player.pauseVideo();
    statusText.textContent='Janela encerrada. A revisão continua pendente.';
    log('window_end',live.currentTime);
  }
}
window.onYouTubeIframeAPIReady = function () {
  log('iframe_api_ready',true);
  player = new YT.Player('source-player',{
    events:{
      onReady:()=>{
        document.getElementById('play').disabled=false;
        document.getElementById('pause').disabled=false;
        statusText.textContent='Player pronto. Pressione Reproduzir.';
        log('player_ready',true);
        timer=setInterval(render,1000);
      },
      onStateChange:e=>log('state',e.data),
      onError:e=>{
        statusText.textContent='Falha no player. Código '+e.data+'. Acesso não comprovado.';
        log('player_error',e.data);
      },
      onAutoplayBlocked:()=>log('autoplay_blocked',true)
    }
  });
};
document.getElementById('load').onclick = () => {
  document.getElementById('load').disabled=true;
  const frame=document.createElement('iframe');
  frame.id='source-player';
  frame.title='Referência j2rk8ycXe3c — player oficial do YouTube';
  frame.referrerPolicy='strict-origin-when-cross-origin';
  frame.allow='autoplay; encrypted-media; picture-in-picture; fullscreen';
  frame.allowFullscreen=true;
  const url=new URL('https://www.youtube.com/embed/'+SOURCE);
  url.search=new URLSearchParams({enablejsapi:'1',origin:location.origin,playsinline:'1',start:'0',end:'40',autoplay:'0',controls:'1'}).toString();
  frame.src=url.href;
  document.getElementById('container').append(frame);
  const api=document.createElement('script');
  api.src='https://www.youtube.com/iframe_api';
  api.onerror=()=>{statusText.textContent='A API do player não carregou.';log('iframe_api_load_failed',true);};
  document.head.append(api);
  statusText.textContent='Carregando o player oficial…';
  log('load_requested',{frameSource:url.href,referrerPolicy:frame.referrerPolicy});
};
document.getElementById('play').onclick=()=>{
  player.unMute();
  player.setVolume(100);
  player.playVideo();
  statusText.textContent='Reprodução solicitada. Imagem e áudio precisam ser comprovados.';
  log('play_requested',true);
};
document.getElementById('pause').onclick=()=>{player.pauseVideo();log('pause_requested',true);};
window.addEventListener('pagehide',()=>{clearInterval(timer);});
render();
