# app.py
from flask import Flask, render_template, request, send_file, redirect, url_for
import os
import shutil
import zipfile
import io
# Importations des bibliothèques nécessaires aux scripts
from obspy import read, Stream
from obspy.io.sac import SACTrace
from datetime import datetime
import requests
from xml.etree import ElementTree
import json
import warnings

# --- Configuration de Flask
app = Flask(__name__)
# Chemin absolu du dossier de travail temporaire
TEMP_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'Data_extraction_temp')

# --- Fonctions de vos scripts (Adaptées pour être appelées en mémoire/dans le serveur) ---

def parse_station_metadata(xml_content):
    # Logique de '0DOWNLOAD_MiniSeed_and_META.py'
    try:
        root = ElementTree.fromstring(xml_content)
        ns = {'ns': 'http://www.fdsn.org/xml/station/1'}
        
        station = root.find('.//ns:Station', ns)
        if station is not None:
            station_code = station.get('code', '').upper()
            metadata = {
                'stla': float(station.find('ns:Latitude', ns).text),
                'stlo': float(station.find('ns:Longitude', ns).text),
                'stel': float(station.find('ns:Elevation', ns).text),
                'channels': []
            }
            
            seen_channels = set()
            
            for channel in root.findall('.//ns:Channel', ns):
                loc_code = channel.get('locationCode', '') or '00'
                chan_code = channel.get('code', '')
                channel_code = f"{loc_code}{chan_code}"
                
                if channel_code not in seen_channels:
                    seen_channels.add(channel_code)
                    
                    azimuth_elem = channel.find('ns:Azimuth', ns)
                    dip_elem = channel.find('ns:Dip', ns)
                    
                    metadata['channels'].append({
                        'kcmpnm': channel_code,
                        'knetwk': "AM",
                        'kstnm': station_code,
                        'cmpaz': float(azimuth_elem.text) if azimuth_elem is not None else -12345.0,
                        'cmpinc': float(dip_elem.text) if dip_elem is not None else -12345.0
                    })
            
            return metadata
    except Exception as e:
        warnings.warn(f"Erreur lors de l'analyse des métadonnées: {e}")
    return None

def fetch_station_metadata(station, starttime, endtime):
    # Logique de '0DOWNLOAD_MiniSeed_and_META.py'
    base_url = "https://data.raspberryshake.org/fdsnws/station/1/query"
    params = {
        "network": "AM",
        "station": station,
        "level": "channel",
        "starttime": starttime,
        "endtime": endtime,
        "format": "xml"
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return parse_station_metadata(response.content)
    except requests.exceptions.RequestException as e:
        warnings.warn(f"Impossible de récupérer les métadonnées pour {station}: {e}")
        return None

def build_query_url(params, station, channel_info):
    # Logique de '0DOWNLOAD_MiniSeed_and_META.py'
    base_url = "https://data.raspberryshake.org/fdsnws/dataselect/1/query"
    location = channel_info['kcmpnm'][0:2]
    channel_code = channel_info['kcmpnm'][2:]
    return f"{base_url}?network=AM&station={station}&location={location}&channel={channel_code}&starttime={params['starttime']}&endtime={params['endtime']}"

def run_processing_pipeline(data):
    """Exécute les étapes 0 à 4 de manière séquentielle"""
    
    # Réinitialiser le dossier temporaire
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    stations = [s.strip() for s in data['stations'].split(',') if s.strip()]
    starttime = data['starttime']
    endtime = data['endtime']
    
    # Logique de '2ENHANCE_META_DATA_with_EVENT.py' (partie saisie utilisateur)
    try:
        evla = float(data['evla'])
        evlo = float(data['evlo'])
        evdp = float(data['evdp'])
        mag = float(data['mag'])
        kevnm = data['kevnm']
        event_time_str = data['event_time']
        
        event_time = datetime.strptime(event_time_str, "%Y-%m-%dT%H:%M:%S")
        nzyear = event_time.year
        nzjday = event_time.timetuple().tm_yday
        nzhour = event_time.hour
        nzmin = event_time.minute
        nzsec = event_time.second
    except ValueError as e:
        return {"success": False, "message": f"Format d'entrée invalide : {e}. Veuillez vérifier les dates/heures et les nombres."}


    # --- Étape 0/1: Téléchargement et Vérification ---
    all_data_ok = True
    
    for station in stations:
        station_metadata = fetch_station_metadata(station, starttime, endtime)
        if not station_metadata or not station_metadata.get('channels'):
            warnings.warn(f"Échec de récupération ou aucun canal pour {station}")
            all_data_ok = False
            continue
            
        for channel in station_metadata['channels']:
            kcmpnm = channel['kcmpnm']
            
            query_params = {'starttime': starttime, 'endtime': endtime}
            url = build_query_url(query_params, station, channel)
            
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                if response.content:
                    safe_starttime = starttime.replace(':', '').replace('-', '')
                    
                    # Sauvegarde MiniSEED
                    mseed_filename = f"{station}_{kcmpnm}_FDSN_{safe_starttime}.mseed"
                    mseed_path = os.path.join(TEMP_DIR, mseed_filename)
                    with open(mseed_path, 'wb') as f:
                        f.write(response.content)
                        
                    # --- Étape 2: Enrichissement des Métadonnées ('2ENHANCE_META_DATA...') ---
                    initial_metadata = {
                        'stla': station_metadata['stla'], 'stlo': station_metadata['stlo'], 'stel': station_metadata['stel'],
                        **channel, 'starttime': starttime, 'endtime': endtime
                    }
                    structured_data = {                    
                        "STATION DATA": {
                            "knetwk": initial_metadata.get("knetwk"),
                            "kstnm": initial_metadata.get("kstnm"),
                            "kcmpnm": initial_metadata.get("kcmpnm"),
                            "cmpaz": initial_metadata.get("cmpaz", -12345.0),
                            "cmpinc": initial_metadata.get("cmpinc", -12345.0),
                            "stla": initial_metadata.get("stla"),
                            "stlo": initial_metadata.get("stlo"),
                            "stel": initial_metadata.get("stel")
                        },
                        "RECORDED DATA": {
                            "starttime": initial_metadata.get("starttime"),
                            "endtime": initial_metadata.get("endtime")
                        },
                        "SISMIC EVENT": {
                            "evla": evla, "evlo": evlo, "evdp": evdp, "mag": mag, "kevnm": kevnm,
                            "nzyear": nzyear, "nzjday": nzjday, "nzhour": nzhour, "nzmin": nzmin, "nzsec": nzsec
                        }
                    }
                    
                    plus_meta_filename = f"{station}_{kcmpnm}_FDSN_{safe_starttime}_META_PLUS.json"
                    plus_meta_path = os.path.join(TEMP_DIR, plus_meta_filename)
                    with open(plus_meta_path, 'w') as mf:
                        json.dump(structured_data, mf, indent=4)

                else:
                    warnings.warn(f"Aucune donnée disponible pour {station} ({kcmpnm})")
                    all_data_ok = False
                    
            except requests.exceptions.RequestException as e:
                warnings.warn(f"Erreur lors de la requête pour {station} ({kcmpnm}): {e}")
                all_data_ok = False
    
    if not all_data_ok and not os.listdir(TEMP_DIR):
         return {"success": False, "message": "Aucune donnée n'a pu être téléchargée pour les stations et la période spécifiées."}


    # --- Étape 3: Création des fichiers SAC ('3CREATE_SAC.py') ---
    
    mseed_files = [f for f in os.listdir(TEMP_DIR) if f.endswith('.mseed')]
    sac_files_created = []

    for mseed_file in mseed_files:
        parts = mseed_file.split('_')
        if len(parts) < 4: continue
            
        base_name = '_'.join(parts[:3])
        time_part = parts[3].split('.')[0]
        json_file = f"{base_name}_{time_part}_META_PLUS.json"
        json_path = os.path.join(TEMP_DIR, json_file)
        
        if not os.path.exists(json_path): continue
        
        try:
            st = read(os.path.join(TEMP_DIR, mseed_file))
            if len(st) == 0: continue
            tr = st[0]
            
            with open(json_path, 'r') as f:
                metadata = json.load(f)
            
            sac = SACTrace.from_obspy_trace(tr)
            station_data = metadata.get('STATION DATA', {})
            event_data = metadata.get('SISMIC EVENT', {})
            recorded_data = metadata.get('RECORDED DATA', {})

            # Paramètres SAC
            sac.knetwk = station_data.get('knetwk', 'AM')
            sac.kstnm = station_data.get('kstnm', '')
            sac.kcmpnm = station_data.get('kcmpnm', '')
            sac.stla = station_data.get('stla', -12345.0)
            sac.stlo = station_data.get('stlo', -12345.0)
            sac.stel = station_data.get('stel', -12345.0)
            sac.cmpaz = station_data.get('cmpaz', -12345.0)
            sac.cmpinc = station_data.get('cmpinc', -12345.0)
            sac.evla = float(event_data.get('evla', -12345.0))
            sac.evlo = float(event_data.get('evlo', -12345.0))
            sac.evdp = float(event_data.get('evdp', -12345.0)) * 1000 # km -> m
            sac.mag = float(event_data.get('mag', -12345.0))
            sac.kevnm = event_data.get('kevnm', 'Event')
            
            # Temps de référence
            start_time = datetime.strptime(recorded_data['starttime'], '%Y-%m-%dT%H:%M:%S')
            sac.nzyear = start_time.year
            sac.nzjday = start_time.timetuple().tm_yday
            sac.nzhour = start_time.hour
            sac.nzmin = start_time.minute
            sac.nzsec = start_time.second
            sac.nzmsec = 0
            sac.b = 0
            
            # Calcul du temps de l'événement (o) par rapport au début de l'enregistrement (b)
            event_time_dt = datetime.strptime(
                f"{event_data['nzyear']}-{event_data['nzjday']} {event_data['nzhour']}:{event_data['nzmin']}:{event_data['nzsec']}",
                "%Y-%j %H:%M:%S"
            )
            sac.o = (event_time_dt - start_time).total_seconds()
            
            sac_file = f"{base_name}_{time_part}.SAC"
            sac_path = os.path.join(TEMP_DIR, sac_file)
            sac.write(sac_path, byteorder='little')
            sac_files_created.append(sac_path)
            
        except Exception as e:
            warnings.warn(f"Erreur lors de la création SAC pour {mseed_file}: {e}")
            
    # Si aucun fichier SAC n'a été créé, c'est que le téléchargement a échoué
    if not sac_files_created:
        return {"success": False, "message": "Le traitement SAC a échoué. Assurez-vous que les fichiers MiniSEED ont été téléchargés correctement."}

    # --- Étape 4: Création des fichiers JSON TectoGlob3D ('4CREATE_JSON_FOR_TECTOGLOB3D.py') ---
    
    # Les choix utilisateur viennent du formulaire
    pointage_ondes = "1" if data['show_wave_times'] == 'o' else "0"
    auto_approximate = data['auto_approximate'] == 'o'
        
    for sac_path in sac_files_created:
        sac_file = os.path.basename(sac_path)
        json_file = os.path.splitext(sac_file)[0] + ".json"
        json_path = os.path.join(TEMP_DIR, json_file)
        
        # Le code Flask force l'auto_approximate à True pour simplifier le formulaire web
        data_tecto = {
            "RESEAU": "EDU-RBSK",
            "EPIVISIBLE": "1",
            "DISTANCEVISIBLE": "0",
            # On met "1" car l'approximation automatique est forcée par le formulaire web
            "POINTAGEONDES": "1", 
            "PmP": -12345,
            "LR": -12345,
        }

        # Écrire le fichier JSON
        try:
            with open(json_path, 'w') as f:
                json.dump(data_tecto, f, indent=4)
        except Exception as e:
            warnings.warn(f"Erreur lors de la création de {json_file}: {e}")
            
    return {"success": True, "message": "Traitement terminé avec succès."}


# --- Routes Flask ---

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        form_data = request.form
        result = run_processing_pipeline(form_data)
        
        if result['success']:
            return redirect(url_for('download_files'))
        else:
            # Passe les données du formulaire en cas d'erreur pour ne pas tout retaper
            return render_template('index.html', error=result['message'], form_data=form_data)
    
    # Le cas GET initial
    return render_template('index.html')


@app.route('/download')
def download_files():
    # Créer une archive ZIP en mémoire pour l'utilisateur
    base_name = f"Donnees_Seismo_TectoGlob3D_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Créer le zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Parcours le dossier temporaire pour ajouter les fichiers
        for root, _, files in os.walk(TEMP_DIR):
            for file in files:
                # N'inclure que les fichiers SAC et JSON pour TectoGlob3D
                if file.endswith('.SAC') or (file.endswith('.json') and '_META_PLUS' not in file):
                    file_path = os.path.join(root, file)
                    # Écrire le fichier dans le ZIP à la racine
                    zf.write(file_path, file)

    zip_buffer.seek(0)
    
    # La destruction du dossier temporaire est faite au début du prochain appel à run_processing_pipeline
    
    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f"{base_name}.zip",
        mimetype='application/zip'
    )

if __name__ == '__main__':
    # Sur Hugging Face, le port doit être 7860
    app.run(host='0.0.0.0', port=7860)