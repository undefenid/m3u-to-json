import re
import json
import sys
from collections import defaultdict

def parse_m3u(file_path):
    groups = defaultdict(lambda: {"logo": "", "items": []})
    current_group = "Sin Grupo"
    current_group_logo = ""
    items = []
    playlist_blocks = []
    
    # Variables para almacenar atributos previos a EXTINF
    pre_license_type = None
    pre_license_key = None
    pre_user_agent = None
    pre_referer = None
    pre_origin = None
    pre_webtoken = None
    
    # Estado para rastrear si estamos procesando un canal
    current_channel = None

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith("#EXTM3U"):
            # Cabecera principal - no hacer nada
            pass
            
        elif line.startswith("#KODIPROP:inputstream.adaptive.license_type"):
            value = line.split("=", 1)[1].strip() if "=" in line else ""
            if current_channel:
                current_channel["licenseType"] = value
            else:
                pre_license_type = value
                
        elif line.startswith("#KODIPROP:inputstream.adaptive.license_key"):
            value = line.split("=", 1)[1].strip() if "=" in line else ""
            if current_channel:
                current_channel["licenseKey"] = value
            else:
                pre_license_key = value
                
        elif line.startswith("#EXTVLCOPT:http-user-agent"):
            value = line.split("=", 1)[1].strip() if "=" in line else ""
            if current_channel:
                current_channel["userAgent"] = value
            else:
                pre_user_agent = value
                
        elif line.startswith("#EXTVLCOPT:http-referrer") or line.startswith("#EXTVLCOPT:http-referer"):
            value = line.split("=", 1)[1].strip() if "=" in line else ""
            if current_channel:
                current_channel["referer"] = value
            else:
                pre_referer = value
                
        elif line.startswith("#EXTINF"):
            # Iniciar un nuevo canal
            current_channel = {}
            
            # Aplicar atributos previos si existen
            if pre_license_type: current_channel["licenseType"] = pre_license_type
            if pre_license_key: current_channel["licenseKey"] = pre_license_key
            if pre_user_agent: current_channel["userAgent"] = pre_user_agent
            if pre_referer: current_channel["referer"] = pre_referer
            if pre_origin: current_channel["origin"] = pre_origin
            if pre_webtoken: current_channel["webtoken"] = pre_webtoken
            
            # Resetear atributos previos
            pre_license_type = None
            pre_license_key = None
            pre_user_agent = None
            pre_referer = None
            pre_origin = None
            pre_webtoken = None
            
            # Extraer atributos de la línea EXTINF
            attrs = {}
            attr_matches = re.findall(r'([a-zA-Z-]+)="([^"]*)"', line)
            for key, value in attr_matches:
                attrs[key] = value
                
            # Determinar si es cabecera de grupo
            is_group_header = "group-logo" in attrs and "group-title" not in attrs
            
            if is_group_header:
                # Es una cabecera de grupo
                current_group_logo = attrs.get("group-logo", "")
            else:
                # Es un canal normal o playlist
                if "group-title" in attrs:
                    current_group = attrs["group-title"]
                    if "group-logo" in attrs:
                        current_group_logo = attrs["group-logo"]
                
                # Extraer nombre del canal
                name_match = re.search(r',(.+)$', line)
                if name_match:
                    current_channel["name"] = name_match.group(1).strip()
                
                # Otros atributos
                current_channel["tvgId"] = attrs.get("tvg-id", "")
                current_channel["tvgName"] = attrs.get("tvg-name", "")
                current_channel["imageUrl"] = attrs.get("tvg-logo", "")
                
                # Manejar tipo de playlist
                if attrs.get("type") == "playlist":
                    current_channel["type"] = "playlist"
        
        elif line and not line.startswith("#") and current_channel:
            # Línea de URL
            if "type" in current_channel and current_channel["type"] == "playlist":
                # Es una playlist
                playlist_blocks.append({
                    "type": "playlist_block",
                    "name": current_channel.get("name", "Playlist"),
                    "url": line
                })
            else:
                # Es un canal normal
                current_channel["url"] = line
                
                # Manejar parámetros adicionales en la URL
                if "|" in line:
                    parts = line.split("|")
                    current_channel["url"] = parts[0]
                    for param in parts[1:]:
                        if "=" in param:
                            key, value = param.split("=", 1)
                            key = key.strip().lower()
                            if key == "user-agent":
                                current_channel["userAgent"] = value
                            elif key == "referer":
                                current_channel["referer"] = value
                            elif key == "origin":
                                current_channel["origin"] = value
                            elif key == "webtoken":
                                current_channel["webtoken"] = value
                
                # Agregar a la lista actual
                groups[current_group]["logo"] = current_group_logo
                groups[current_group]["items"].append(current_channel)
            
            # Finalizar el canal actual
            current_channel = None
        
        i += 1

    # Construir estructura final
    result = []
    
    # Agregar grupos
    for group_title, group_data in groups.items():
        result.append({
            "type": "group_block",
            "groupTitle": group_title,
            "groupLogo": group_data["logo"],
            "items": [
                {
                    "name": item["name"],
                    "url": item["url"],
                    "imageUrl": item.get("imageUrl", ""),
                    "tvgId": item.get("tvgId", ""),
                    "tvgName": item.get("tvgName", ""),
                    "licenseType": item.get("licenseType", ""),
                    "licenseKey": item.get("licenseKey", ""),
                    "userAgent": item.get("userAgent", ""),
                    "referer": item.get("referer", ""),
                    "origin": item.get("origin", ""),
                    "webtoken": item.get("webtoken", "")
                } for item in group_data["items"]
            ]
        })
    
    # Agregar playlists
    result.extend(playlist_blocks)
    
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python m3u_to_json.py <input.m3u> [output.json]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "output.json"
    
    json_data = parse_m3u(input_file)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    print(f"Conversión completada. Archivo guardado como: {output_file}")
