"""Arayüzü headless Chromium'da sahte köprüyle açar, hata yakalar ve ekran görüntüsü alır."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]; OUT = Path("/tmp/shots"); OUT.mkdir(exist_ok=True)
SVG = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgNjAiPjxwYXRoIGQ9Ik0xMCA1MCBDMTAgMTAgNDAgNSA2MCAyMCBTOTAgMzAgODAgNTAgWiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMjIyIiBzdHJva2Utd2lkdGg9IjQiLz48L3N2Zz4="
MOCK = r"""
(function(){
const ok=d=>({ok:true,data:d});
const tracks=[{track:'Imola',layout:'GP',event_name:'GP Time Attack',track_length:4909,mod:false},{track:'Monza',layout:'GP',event_name:'GP',track_length:5793,mod:false},{track:'Suzuka',layout:'East',event_name:'East',track_length:2243,mod:false},{track:'ek_tsukub_qu',layout:'freeroam',event_name:'freeroam Time Attack',track_length:2045,mod:true,mod_folder:'ek_tsukub_qu'}];
const cars=[{name:'preset_m4gt3_mech_1',display_name:'BMW M4 GT3',performance_indicator:82.5,mod:false},{name:'preset_a110s_mech_1',display_name:'Alpine A110 S',performance_indicator:61.0,mod:false},{name:'my_mod_car',display_name:'My Mod Car',performance_indicator:70,mod:true}];
const base={id:'server_1',name:'traffickarayevo',tcp_port:9700,udp_port:9700,http_port:8080,max_players:8,cycle:true,driver_password:'',spectator_password:'',admin_password:'admin',type:'MultiplayerServerListSessionType_RANKED',game_type:'GameModeType_RACE_WEEKEND',track:'ek_tsukub_qu',layout:'freeroam',event_name:'freeroam Time Attack',track_length:2045,track_is_mod:true,weather:'GameModeSelectionWeatherType_CLEAR',weather_behavior:'GameModeSelectionWeatherBehaviour_STATIC',initial_grip:'InitialGrip_GREEN',year:2024,month:8,day:15,second:0,cars:[{car_name:'preset_m4gt3_mech_1',ballast:10,restrictor:0}],netcode_update_interval:55,tuning_type:'TuningAllowed',pi_min:0,pi_max:0,export_json:false,serverconfig_extra:{},seasondefinition_extra:{},log_file_path:'C:/x/log.txt',results_path:'C:/x/result',extra_arguments:'',custom_command:'',race_duration_type:'GameModeSelectionDuration_TIME',min_waiting_for_players:10,max_waiting_for_players:30,mandatory_pitstop:false,mandatory_pitstop_tyre_change:false,mandatory_pitstop_refuel:false,pit_window_time:600,entry_list_server_url:'',token:'',entry_list_path:'',results_post_url:''};
for(const p of ['practice','qualify','warmup','race']){base[p+'_length']=300;base[p+'_hour']=16;base[p+'_minute']=0;base[p+'_time_multiplier']=1;base[p+'_max_wait_to_box']=10;base[p+'_overtime']=10;}
let running=false,seq=0;const lines=[];
function push(k,t){seq++;lines.push([seq,'17:58:53',k,t]);}
push('sys',"▶ 'traffickarayevo' başlatılıyor (pist: ek_tsukub_qu / freeroam, port: 9700)");push('out','[info] Build release 0.9.1, steam appid 3058630');push('out','[server] [info] Start Server traffickarayevo');push('out','[error] Exception thrown: Trying to load a message with an empty path');push('err','■ Sunucu beklenmedik şekilde kapandı (çıkış kodu 1).');
const diag=[{level:'error',title:'Sunucu seçilen pisti/içeriği bulamadı',detail:'Genelde mod sunucunun kendi klasöründe yoktur.',action:'mods'}];
const modItem=(kind,name,extra)=>Object.assign({kind,name,path:'C:/m/'+name,in_game:true,in_server:name!=='b_mod',size:376251188,has_map:true,has_preview:true,layouts:['freeroam'],track_text:'{"layout":"freeroam"}',entry:kind==='track'?{track:name,layout:'freeroam',event_name:'freeroam Time Attack',track_length:2045,max_pit_slot:20}:{name,display_name:'My Mod Car',performance_indicator:70,property_1:1,property_2:2,property_3:3}},extra||{});
const A={
boot:()=>ok({app:'Apex Server Manager',version:'3.0.0',setup_done:window.__setup!==false,ip:'192.168.1.20',settings:{}}),
tick:()=>ok({running:running?['server_1']:[],events:window.__events?window.__events.splice(0):[]}),
list_servers:()=>ok([Object.assign({},base,{running,cars:1}),Object.assign({},base,{id:'server_2',name:'Sunucu 2',track:'Imola',layout:'GP',track_is_mod:false,game_type:'GameModeType_PRACTICE',running:false,tcp_port:9701})]),
get_server:()=>ok({data:JSON.parse(JSON.stringify(base)),tracks,cars,ip:'192.168.1.20'}),
save_server:()=>ok({warnings:[]}),
start_server:()=>{running=true;push('sys','Süreç başladı (PID 24544)');return ok('job1');},
job_status:()=>ok({id:'job1',done:true,error:'',percent:100,msg:'tamam',logs:[],result:true}),
stop_server:()=>{running=false;return ok(true);},
console:(sid,since)=>ok({lines:lines.filter(l=>l[0]>since),seq,running,pid:running?24544:null,started:Date.now()/1000-75,now:Date.now()/1000,exit_code:running?null:1,diagnosis:diag}),
console_clear:()=>ok(true),results:()=>ok([]),
list_mods:()=>ok({tracks:[modItem('track','ek_tsukub_qu'),modItem('track','b_mod')],cars:[modItem('car','my_mod_car')],game_root:'C:/g',server_root:'C:/s',mirror:true}),
mod_map:()=>ok(window.__svg),
default_roots:()=>ok({mods_root:'C:\\Users\\Administrator\\Saved Games\\ACE\\mods',server_mods_root:'C:\\Users\\Administrator\\Saved Games\\ACE-Server\\mods',server_path:'',steam_user:'',app_id:4564210}),
detect_servers:()=>ok(['C:\\Program Files (x86)\\Steam\\steamapps\\common\\Assetto Corsa EVO Dedicated Server']),
validate_server_path:p=>ok({ok:!!p,message:p?'Geçerli EVO Dedicated Server klasörü.':'Klasör seçilmedi.'}),
get_settings:()=>ok({evo_server_path:'C:\\Steam\\EVO Server',mods_root:'C:\\Users\\A\\Saved Games\\ACE\\mods',server_mods_root:'C:\\Users\\A\\Saved Games\\ACE-Server\\mods',mirror_mods_to_server:true,auto_restart:false,auto_restart_max:3,inject_mod_events:true,steam_user:''}),
};
window.pywebview={api:new Proxy({},{get:(_,n)=>async(...a)=>{if(!A[n])return ok(null);return A[n](...a);}})};
})();
"""
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1380, "height": 860})
    pg.on("pageerror", lambda e: errors.append("PAGEERROR " + str(e)))
    pg.on("console", lambda m: errors.append("CONSOLE " + m.text) if m.type == "error" else None)
    pg.add_init_script(MOCK + f"window.__svg={json.dumps(SVG)};window.__setup={'false' if 'setup' in sys.argv else 'true'};window.__events=[];")
    pg.goto("file://" + str(ROOT / "web" / "index.html")); pg.wait_for_timeout(700)
    def shot(name): pg.wait_for_timeout(450); pg.screenshot(path=str(OUT / f"{name}.png"))
    if "setup" in sys.argv:
        shot("setup1"); pg.click("text=Başlayalım"); shot("setup2"); pg.click("text=Devam"); shot("setup3"); pg.click("text=Devam"); shot("setup4")
    else:
        shot("servers")
        pg.click(".scard >> nth=0"); shot("srv_console")
        for tab in ["Genel", "Oturumlar", "Pist", "Hava ve zemin", "Araçlar", "Gelişmiş"]:
            pg.click(f".tab[data-n='{tab}']"); shot("tab_" + tab.split()[0])
        pg.click(".tab[data-n='Konsol']"); pg.click("button:has-text('Başlat')"); pg.wait_for_timeout(900); shot("srv_running")
        pg.click(".navbtn[data-r='mods']"); shot("mods"); pg.click("button:has-text('Araçlar')"); shot("mods_cars")
        pg.click("button:has-text('Pistler')"); pg.click("button:has-text('Düzenle') >> nth=0"); shot("mods_edit"); pg.click("button:has-text('Vazgeç')")
        pg.click(".navbtn[data-r='settings']"); shot("settings")
        pg.evaluate("window.__events.push({type:'drop',sources:[{path:'C:/x/ek_tsukub_qu.7z',name:'ek_tsukub_qu.7z',error:'',is_archive:true,items:[{kind:'track',name:'ek_tsukub_qu',installed:true}]}]})"); pg.wait_for_timeout(1300); shot("dropcard")
    b.close()
print("\n".join(errors) if errors else "JS HATASI YOK")
