"""
servidor.py — Nucleo do sistema de biblioteca distribuida
Aceita conexoes TCP, gerencia threads, mutex, semaforo, fila FIFO + worker.
Mesma arquitetura do projeto de Controle de Estoque Distribuido (C).
"""

import socket
import threading
import pickle
import os
import time
from collections import deque
from datetime import datetime

HOST = "0.0.0.0"
PORT = 8086
DATA_FILE = os.environ.get("DATA_FILE", "biblioteca.dat")
LOG_DIR = os.environ.get("LOG_DIR", ".")

FILA_MAX = 256

# ── Estado em memoria (equivalente ao lista[100] do C) ──────────────
livros = []      # cada item: {"id", "titulo", "autor", "status"}
usuarios = []     # cada item: {"id", "nome"}
emprestimos = []  # cada item: {"id", "usuario_id", "livro_id", "data"}

proximo_id_livro = 1
proximo_id_usuario = 1
proximo_id_emprestimo = 1

# ── Sincronizacao (igual ao servidor.c) ──────────────────────────────
mutex_acervo = threading.Lock()        # protege livros/usuarios/emprestimos
mutex_fila = threading.Lock()          # protege a fila de reservas
mutex_log = threading.Lock()           # protege escrita do log
semaforo_leitura = threading.Semaphore(2)  # max 2 leitores simultaneos
cond_fila = threading.Condition(mutex_fila)  # acorda o worker

fila_reservas = deque()  # fila FIFO circular (equivalente a FilaCompras)

arq_log = None
ip_proprio = "0.0.0.0"


# ── Identificacao de origem (cliente / admin / servidor) ─────────────
def origem(ip, tipo):
    """Formata IP + tipo de quem fez a requisicao, para deixar o log claro."""
    return f"{ip} ({tipo})"


# ── Log thread-safe (igual ao log_fmt do C) ───────────────────────────
def log(tag, msg):
    global arq_log
    linha = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][{tag}] {msg}"
    print(linha, flush=True)
    with mutex_log:
        if arq_log:
            arq_log.write(linha + "\n")
            arq_log.flush()


def descobrir_ip_proprio():
    """Descobre o IP do proprio servidor na rede Docker, igual ao descobrir_ip_proprio() do C."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


# ── Persistencia (igual a carregar_dados / salvar_dados do C) ───────
def carregar_dados():
    global livros, usuarios, emprestimos
    global proximo_id_livro, proximo_id_usuario, proximo_id_emprestimo
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as f:
            estado = pickle.load(f)
        livros = estado["livros"]
        usuarios = estado["usuarios"]
        emprestimos = estado["emprestimos"]
        proximo_id_livro = estado["proximo_id_livro"]
        proximo_id_usuario = estado["proximo_id_usuario"]
        proximo_id_emprestimo = estado["proximo_id_emprestimo"]
        log("INIT", f"Dados carregados de {DATA_FILE}: {len(livros)} livro(s), {len(usuarios)} usuario(s)")
    else:
        log("INIT", f"Nenhum {DATA_FILE} encontrado. Iniciando vazio.")


def salvar_dados():
    estado = {
        "livros": livros,
        "usuarios": usuarios,
        "emprestimos": emprestimos,
        "proximo_id_livro": proximo_id_livro,
        "proximo_id_usuario": proximo_id_usuario,
        "proximo_id_emprestimo": proximo_id_emprestimo,
    }
    with open(DATA_FILE, "wb") as f:
        pickle.dump(estado, f)


# ── Worker da fila de reservas (igual ao worker_compras do C) ───────
def worker_reservas():
    log("WORKER", f"Worker de reservas iniciado | servidor={ip_proprio}")
    while True:
        with cond_fila:
            while not fila_reservas:
                cond_fila.wait()
            reserva = fila_reservas.popleft()
            log("FILA", f"Desenfileirado pelo worker | usuario_id={reserva['usuario_id']} livro_id={reserva['livro_id']} | fila restante={len(fila_reservas)}")

        with mutex_acervo:
            log("MUTEX", f"Travando acervo | origem=worker (servidor={ip_proprio}) | verificando livro_id={reserva['livro_id']}")
            livro = _buscar_livro(reserva["livro_id"])
            atendida = False
            if livro and livro["status"] == "disponivel":
                _emprestar(reserva["usuario_id"], reserva["livro_id"])
                atendida = True
                log("WORKER", f"Reserva atendida automaticamente | usuario_id={reserva['usuario_id']} recebeu livro_id={reserva['livro_id']} ('{livro['titulo']}')")
            log("MUTEX", f"Liberando acervo | origem=worker (servidor={ip_proprio})")

        if not atendida:
            with cond_fila:
                fila_reservas.append(reserva)
            log("WORKER", f"Livro_id={reserva['livro_id']} ainda indisponivel | reserva de usuario_id={reserva['usuario_id']} volta para o fim da fila")
            time.sleep(1)  # evita busy-loop quando o livro continua indisponivel


def _buscar_livro(livro_id):
    for l in livros:
        if l["id"] == livro_id:
            return l
    return None


def _buscar_usuario(usuario_id):
    for u in usuarios:
        if u["id"] == usuario_id:
            return u
    return None


def _emprestar(usuario_id, livro_id):
    global proximo_id_emprestimo
    livro = _buscar_livro(livro_id)
    livro["status"] = "emprestado"
    emprestimos.append({
        "id": proximo_id_emprestimo,
        "usuario_id": usuario_id,
        "livro_id": livro_id,
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    proximo_id_emprestimo += 1
    salvar_dados()


# ── Opcodes do protocolo (igual ao tratar_conexao do C) ──────────────
# Cliente:  0=listar livros | 2=alugar | 3=devolver | 4=listar fila | 20=listar usuarios | 21=reservar
# Admin:   10=listar livros | 11=cadastrar livro | 12=excluir livro
#          13=cadastrar usuario | 14=excluir usuario | 15=listar emprestimos
#          16=listar fila | 17=listar usuarios

def processar(req, ip, tipo):
    op = req.get("op")
    src = origem(ip, tipo)

    # ── op=0/10: listar livros (semaforo) ─────────────────────────
    if op == 0 or op == 10:
        log("SEM", f"Aguardando vaga de leitura | origem={src}")
        with semaforo_leitura:
            log("SEM", f"Leitura iniciada | origem={src}")
            with mutex_acervo:
                copia = [dict(l) for l in livros]
            log("SEM", f"Leitura finalizada | origem={src} | {len(copia)} livro(s) retornado(s)")
        return {"ok": True, "livros": copia}

    # ── op=20/17: listar usuarios ──────────────────────────────────
    if op == 20 or op == 17:
        log("CRUD", f"Listagem de usuarios solicitada | origem={src}")
        with mutex_acervo:
            copia = [dict(u) for u in usuarios]
        return {"ok": True, "usuarios": copia}

    # ── op=2: alugar livro ──────────────────────────────────────────
    if op == 2:
        usuario_id = req["usuario_id"]
        livro_id = req["livro_id"]
        with mutex_acervo:
            log("MUTEX", f"Travando acervo | origem={src} | tentando alugar livro_id={livro_id} para usuario_id={usuario_id}")
            usuario = _buscar_usuario(usuario_id)
            livro = _buscar_livro(livro_id)
            if not usuario:
                log("MUTEX", f"Liberando acervo | origem={src} | usuario_id={usuario_id} nao encontrado")
                return {"ok": False, "msg": "Usuario nao encontrado."}
            if not livro:
                log("MUTEX", f"Liberando acervo | origem={src} | livro_id={livro_id} nao encontrado")
                return {"ok": False, "msg": "Livro nao encontrado."}
            if livro["status"] != "disponivel":
                log("MUTEX", f"Liberando acervo | origem={src} | livro_id={livro_id} ('{livro['titulo']}') indisponivel")
                return {"ok": False, "msg": "Livro indisponivel.", "indisponivel": True}
            _emprestar(usuario_id, livro_id)
            log("MUTEX", f"Aluguel confirmado | origem={src} | usuario_id={usuario_id} <- livro_id={livro_id} ('{livro['titulo']}')")
            log("MUTEX", f"Liberando acervo | origem={src}")
        return {"ok": True, "msg": "Aluguel confirmado!"}

    # ── op=21: entrar na fila de reserva ─────────────────────────────
    if op == 21:
        usuario_id = req["usuario_id"]
        livro_id = req["livro_id"]
        with cond_fila:
            if len(fila_reservas) >= FILA_MAX:
                log("FILA", f"Fila cheia | origem={src} | reserva recusada")
                return {"ok": False, "msg": "Fila cheia."}
            fila_reservas.append({"usuario_id": usuario_id, "livro_id": livro_id})
            pos = len(fila_reservas)
            log("FILA", f"Enfileirado | origem={src} | usuario_id={usuario_id} livro_id={livro_id} | posicao={pos}/{FILA_MAX}")
            cond_fila.notify()
        return {"ok": True, "msg": f"Reserva enfileirada (posicao {pos}).", "posicao": pos}

    # ── op=3: devolver livro ─────────────────────────────────────────
    if op == 3:
        livro_id = req["livro_id"]
        with mutex_acervo:
            log("MUTEX", f"Travando acervo | origem={src} | devolvendo livro_id={livro_id}")
            livro = _buscar_livro(livro_id)
            if not livro:
                log("MUTEX", f"Liberando acervo | origem={src} | livro_id={livro_id} nao encontrado")
                return {"ok": False, "msg": "Livro nao encontrado."}
            if livro["status"] != "emprestado":
                log("MUTEX", f"Liberando acervo | origem={src} | livro_id={livro_id} nao estava emprestado")
                return {"ok": False, "msg": "Este livro nao esta emprestado."}
            livro["status"] = "disponivel"
            for e in emprestimos:
                if e["livro_id"] == livro_id and "devolvido" not in e:
                    e["devolvido"] = True
            salvar_dados()
            log("MUTEX", f"Devolucao confirmada | origem={src} | livro_id={livro_id} ('{livro['titulo']}') disponivel novamente")
            log("MUTEX", f"Liberando acervo | origem={src}")
        with cond_fila:
            cond_fila.notify_all()
        return {"ok": True, "msg": "Devolucao registrada."}

    # ── op=4/16: listar fila ──────────────────────────────────────────
    if op == 4 or op == 16:
        log("FILA", f"Listagem da fila solicitada | origem={src}")
        with mutex_fila:
            copia = list(fila_reservas)
        return {"ok": True, "fila": copia}

    # ── op=11: cadastrar livro (admin) ───────────────────────────────
    if op == 11:
        global proximo_id_livro
        titulo = req["titulo"]
        autor = req["autor"]
        with mutex_acervo:
            log("MUTEX", f"Travando acervo | origem={src} | cadastrando livro")
            novo = {"id": proximo_id_livro, "titulo": titulo, "autor": autor, "status": "disponivel"}
            livros.append(novo)
            proximo_id_livro += 1
            salvar_dados()
            log("CRUD", f"Livro cadastrado | origem={src} | id={novo['id']} titulo='{titulo}' autor='{autor}'")
            log("MUTEX", f"Liberando acervo | origem={src}")
        return {"ok": True, "msg": f"Livro cadastrado (id={novo['id']}).", "id": novo["id"]}

    # ── op=12: excluir livro (admin) ──────────────────────────────────
    if op == 12:
        livro_id = req["livro_id"]
        with mutex_acervo:
            log("MUTEX", f"Travando acervo | origem={src} | excluindo livro_id={livro_id}")
            livro = _buscar_livro(livro_id)
            if not livro:
                log("MUTEX", f"Liberando acervo | origem={src} | livro_id={livro_id} nao encontrado")
                return {"ok": False, "msg": "Livro nao encontrado."}
            if livro["status"] == "emprestado":
                log("MUTEX", f"Liberando acervo | origem={src} | livro_id={livro_id} esta emprestado, exclusao bloqueada")
                return {"ok": False, "msg": "Nao e possivel excluir livro emprestado."}
            livros.remove(livro)
            salvar_dados()
            log("CRUD", f"Livro excluido | origem={src} | id={livro_id} titulo='{livro['titulo']}'")
            log("MUTEX", f"Liberando acervo | origem={src}")
        return {"ok": True, "msg": "Livro excluido."}

    # ── op=13: cadastrar usuario (admin) ──────────────────────────────
    if op == 13:
        global proximo_id_usuario
        nome = req["nome"]
        with mutex_acervo:
            log("MUTEX", f"Travando acervo | origem={src} | cadastrando usuario")
            novo = {"id": proximo_id_usuario, "nome": nome}
            usuarios.append(novo)
            proximo_id_usuario += 1
            salvar_dados()
            log("CRUD", f"Usuario cadastrado | origem={src} | id={novo['id']} nome='{nome}'")
            log("MUTEX", f"Liberando acervo | origem={src}")
        return {"ok": True, "msg": f"Usuario cadastrado (id={novo['id']}).", "id": novo["id"]}

    # ── op=14: excluir usuario (admin) ─────────────────────────────────
    if op == 14:
        usuario_id = req["usuario_id"]
        with mutex_acervo:
            log("MUTEX", f"Travando acervo | origem={src} | excluindo usuario_id={usuario_id}")
            usuario = _buscar_usuario(usuario_id)
            if not usuario:
                log("MUTEX", f"Liberando acervo | origem={src} | usuario_id={usuario_id} nao encontrado")
                return {"ok": False, "msg": "Usuario nao encontrado."}
            ativos = [e for e in emprestimos if e["usuario_id"] == usuario_id and "devolvido" not in e]
            if ativos:
                log("MUTEX", f"Liberando acervo | origem={src} | usuario_id={usuario_id} possui emprestimos ativos, exclusao bloqueada")
                return {"ok": False, "msg": "Usuario possui emprestimos ativos."}
            usuarios.remove(usuario)
            salvar_dados()
            log("CRUD", f"Usuario excluido | origem={src} | id={usuario_id} nome='{usuario['nome']}'")
            log("MUTEX", f"Liberando acervo | origem={src}")
        return {"ok": True, "msg": "Usuario excluido."}

    # ── op=15: listar emprestimos ativos (admin) ────────────────────
    if op == 15:
        log("CRUD", f"Listagem de emprestimos ativos solicitada | origem={src}")
        with mutex_acervo:
            ativos = [e for e in emprestimos if "devolvido" not in e]
            copia = []
            for e in ativos:
                u = _buscar_usuario(e["usuario_id"])
                l = _buscar_livro(e["livro_id"])
                copia.append({
                    "id": e["id"],
                    "usuario": u["nome"] if u else "?",
                    "livro": l["titulo"] if l else "?",
                    "data": e["data"],
                })
        return {"ok": True, "emprestimos": copia}

    log("WARN", f"Opcode invalido recebido | origem={src} | op={op}")
    return {"ok": False, "msg": f"Opcode invalido: {op}"}


# ── Thread de conexao (igual a tratar_conexao do C) ──────────────────
def tratar_conexao(conn, addr):
    ip = addr[0]
    try:
        dados = b""
        while not dados.endswith(b"\n"):
            parte = conn.recv(4096)
            if not parte:
                break
            dados += parte
        if not dados:
            return
        req = pickle.loads(dados.rstrip(b"\n"))
        tipo = req.get("origem", "desconhecido")
        resp = processar(req, ip, tipo)
        conn.sendall(pickle.dumps(resp) + b"\n")
    except (ConnectionResetError, BrokenPipeError, EOFError):
        pass
    finally:
        conn.close()


# ── Loop de accept (igual ao loop_accept do C) ───────────────────────
def loop_accept(server):
    while True:
        conn, addr = server.accept()
        # o tipo de origem so e' conhecido apos ler o payload, entao o
        # log de CONN aqui mostra so o IP; o log detalhado de cada acao
        # (dentro de processar) mostra IP + tipo (cliente/admin/worker).
        log("CONN", f"Conexao aceita | ip={addr[0]} | servidor={ip_proprio}:{PORT}")
        t = threading.Thread(target=tratar_conexao, args=(conn, addr), daemon=True)
        t.start()


def main():
    global arq_log, ip_proprio
    ip_proprio = descobrir_ip_proprio()

    os.makedirs(LOG_DIR, exist_ok=True)
    arq_log = open(os.path.join(LOG_DIR, "servidor.log"), "a")

    log("INIT", "=" * 50)
    log("INIT", f"SERVIDOR BIBLIOTECA — IP: {ip_proprio} | PORTA: {PORT}")
    log("INIT", "=" * 50)

    carregar_dados()

    worker = threading.Thread(target=worker_reservas, daemon=True)
    worker.start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(50)

    log("INIT", f"Servidor escutando em {HOST}:{PORT} (IP real: {ip_proprio})")
    loop_accept(server)


if __name__ == "__main__":
    main()