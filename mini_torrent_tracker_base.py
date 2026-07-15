"""
ACTIVIDAD - Mini-Torrent P2P CON TRACKER (para completar)
=========================================================
Igual que el mini-torrent, pero el descargador YA NO recibe las direcciones a
mano: se las pregunta a un TRACKER (una "DHT de juguete", ver presentación Grupo 1).

  - Las semillas se ANUNCIAN al tracker: "yo tengo el archivo, estoy en ip:puerto".
  - El descargador PREGUNTA al tracker: "¿quién tiene el archivo?".

Así se resuelve el problema central del P2P: localizar quién tiene el recurso
sin saberlo de antemano (en BitTorrent lo hace el tracker / DHT; en IPFS, los
provider records sobre Kademlia).

Completa los 4 TODO. Cómo probar: ver ACTIVIDAD_MINI_TORRENT_TRACKER.md
(o ejecuta DEMO_tracker.bat con la solución ya hecha).

Roles:
  tracker   -> directorio: registra semillas y responde quién tiene el archivo.
  seeder    -> se anuncia al tracker y reparte los trozos del archivo.
  descargar -> le pregunta al tracker quién tiene el archivo y descarga de ellos.
"""

import socket
import sys
import hashlib

TAM_BLOQUE = 64


def partir(ruta):
    with open(ruta, "rb") as f:
        datos = f.read()
    return [datos[i:i + TAM_BLOQUE] for i in range(0, len(datos), TAM_BLOQUE)]


def cid(bloque):
    return hashlib.sha1(bloque).hexdigest()[:8]


def recibir_todo(conexion):
    datos = b""
    while True:
        parte = conexion.recv(4096)
        if not parte:
            break
        datos += parte
    return datos


def pedir(peer, mensaje):
    ip, puerto = peer.split(":")
    s = socket.socket()
    s.connect((ip, int(puerto)))
    s.sendall(mensaje.encode())
    datos = recibir_todo(s)
    s.close()
    return datos


rol = sys.argv[1]

if rol == "tracker":
    puerto = int(sys.argv[2])
    registro = set()          # conjunto de "ip:puerto" de las semillas conocidas

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", puerto))
    s.listen()
    print(f"Tracker (DHT de juguete) activo en el puerto {puerto}.")

    while True:
        conexion, direccion = s.accept()
        pedido = conexion.recv(1024).decode()

        if pedido.startswith("ANNOUNCE "):
            puerto_semilla = pedido.split()[1]

            # TODO 1: guarda la semilla en el registro como "ip:puerto".
            #   la IP es direccion[0]; el puerto es puerto_semilla.
            #   pista: registro.add(f"{direccion[0]}:{puerto_semilla}")
            registro.add(f"{direccion[0]}:{puerto_semilla}")

            conexion.sendall(b"OK")
            print(f"  + semilla registrada: {direccion[0]}:{puerto_semilla}   (total: {len(registro)})")

        elif pedido == "PEERS":
            # TODO 2: responde con la lista de semillas separadas por espacio.
            #   pista: conexion.sendall(" ".join(registro).encode())
            conexion.sendall(" ".join(registro).encode())

        conexion.close()

elif rol == "seeder":
    puerto = int(sys.argv[2])
    archivo = sys.argv[3]
    tracker = sys.argv[4]        # "ip:puerto" del tracker
    bloques = partir(archivo)

    # TODO 3: anúnciate al tracker diciéndole tu puerto.
    #   pista: pedir(tracker, f"ANNOUNCE {puerto}")
    pedir(tracker, f"ANNOUNCE {puerto}")

    print(f"Me anuncié al tracker {tracker}.")

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", puerto))
    s.listen()
    print(f"Semilla activa en el puerto {puerto}: tengo {len(bloques)} bloques de '{archivo}'.")

    while True:
        conexion, _ = s.accept()
        pedido = conexion.recv(1024).decode()

        if pedido == "INFO":
            manifiesto = str(len(bloques)) + " " + " ".join(cid(b) for b in bloques)
            conexion.sendall(manifiesto.encode())

        elif pedido.startswith("GET "):
            i = int(pedido.split()[1])
            conexion.sendall(bloques[i])
            print(f"  -> entregué el bloque {i} (cid {cid(bloques[i])})")

        conexion.close()

elif rol == "descargar":
    salida = sys.argv[2]
    tracker = sys.argv[3]        # "ip:puerto" del tracker

    # TODO 4: pregúntale al tracker quién tiene el archivo.
    #   pista: respuesta = pedir(tracker, "PEERS").decode().strip()
    respuesta = pedir(tracker, "PEERS").decode().strip()

    peers = respuesta.split() if respuesta else []
    if not peers:
        print("El tracker no conoce ninguna semilla. Levanta los seeders primero.")
        sys.exit(1)
    print(f"El tracker me dio {len(peers)} semilla(s): {peers}\n")

    info = pedir(peers[0], "INFO").decode().split()
    n = int(info[0])
    hashes = info[1:]
    print(f"El archivo tiene {n} bloques. Descargando...\n")

    bloques = []
    for i in range(n):
        peer = peers[i % len(peers)]
        bloque = pedir(peer, f"GET {i}")
        ok = (cid(bloque) == hashes[i])
        estado = "OK" if ok else "CORRUPTO!"
        print(f"bloque {i}  <-  {peer}   cid {cid(bloque)}   [{estado}]")
        if not ok:
            print("\n¡Falló la verificación de integridad! Abortando.")
            sys.exit(1)
        bloques.append(bloque)

    with open(salida, "wb") as f:
        f.write(b"".join(bloques))
    print(f"\nArchivo reconstruido: '{salida}'")
    print("El descargador encontró las semillas vía el tracker y verificó cada bloque por su hash.")

else:
    print("Rol no válido. Usa 'tracker', 'seeder' o 'descargar'.")
