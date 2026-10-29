"""Fullscreen chrome shared by signage frames."""
from pathlib import Path

def screen(body,platform=False):
    mode='platform' if platform else 'realtime'
    style='''<style>html,body{width:100%;margin:0;background:#edf5f8}body{overflow-x:hidden}.screen-action{position:static;flex-shrink:0;white-space:nowrap;margin-left:10px;z-index:10000;border:1px solid #cbdce9;background:white;color:#175a93;border-radius:9px;padding:9px 14px;font:600 13px system-ui;cursor:pointer}body{padding-top:0}.screen-active{overflow:hidden!important;padding-top:0!important}.screen-active .screen-action{position:fixed;right:12px;top:10px;margin:0;opacity:.65}.screen-active .screen-action:hover{opacity:1}.screen-active .screen-fit{position:absolute;transform-origin:top left;max-width:none!important;margin:0!important;box-sizing:border-box}.screen-active .method{display:none}.screen-active .sg-layout{grid-template-columns:minmax(0,3fr) minmax(300px,1fr)}.screen-active .map svg{max-height:620px}.screen-active .sg-head{padding-right:160px}</style>'''
    return style+body+'<button class="screen-action" id="signage-fullscreen">⛶ 전체화면</button><script>window.signageScreenMode="'+mode+'";</script><script>'+(Path(__file__).parent/'signage_screen.js').read_text()+'</script>'
