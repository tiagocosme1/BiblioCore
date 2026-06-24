"""
cliente.py — Interface de aluguel de livros
Modo interativo (menu) e modo automatico (MODO_AUTO=1, usado pela simulacao).
"""

import socket
import pickle
import os
import sys
import time

SERVIDOR_HOST = os.environ.get("SERVIDOR_HOST", "127.0.0.1")
SERVIDOR_PORT = int(os.environ.get("SERVIDOR_PORT", "8086"))


def enviar(req):
    req["origem"] = "cliente"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SERVIDOR_HOST, SERVIDOR_PORT))
        s.sendall(pickle.dumps(req) + b"\n")
        dados = b""
        while not dados.endswith(b"\n"):
            parte = s.recv(4096)
            if not parte:
                break
            dados += parte
        return pickle.loads(dados.rstrip(b"\n"))


def listar_livros():
    resp = enviar({"op": 0})
    livros = resp.get("livros", [])
    print("\n  ID  TITULO                          AUTOR                STATUS")
    print("  " + "-" * 70)
    for l in livros:
        status = "Disponivel" if l["status"] == "disponivel" else "Emprestado"
        print(f"  {l['id']:<4}{l['titulo'][:30]:<32}{l['autor'][:20]:<21}{status}")
    if not livros:
        print("  (nenhum livro cadastrado)")
    return livros


def listar_usuarios():
    resp = enviar({"op": 20})
    usuarios = resp.get("usuarios", [])
    print("\n  ID  NOME")
    print("  " + "-" * 30)
    for u in usuarios:
        print(f"  {u['id']:<4}{u['nome']}")
    if not usuarios:
        print("  (nenhum usuario cadastrado — peca ao admin para cadastrar)")
    return usuarios


def alugar_livro():
    livros = listar_livros()
    if not livros:
        return
    usuarios = listar_usuarios()
    if not usuarios:
        return
    try:
        uid = int(input("\n  Seu ID de usuario: "))
        lid = int(input("  ID do livro: "))
    except ValueError:
        print("  ID invalido.")
        return
    resp = enviar({"op": 2, "usuario_id": uid, "livro_id": lid})
    print(f"  {'OK' if resp['ok'] else 'ERRO'}: {resp['msg']}")
    if not resp["ok"] and resp.get("indisponivel"):
        escolha = input("  Livro indisponivel. Deseja entrar na fila de reserva? (S/N): ")
        if escolha.strip().upper() == "S":
            resp2 = enviar({"op": 21, "usuario_id": uid, "livro_id": lid})
            print(f"  {'OK' if resp2['ok'] else 'ERRO'}: {resp2['msg']}")


def devolver_livro():
    try:
        lid = int(input("  ID do livro a devolver: "))
    except ValueError:
        print("  ID invalido.")
        return
    resp = enviar({"op": 3, "livro_id": lid})
    print(f"  {'OK' if resp['ok'] else 'ERRO'}: {resp['msg']}")


def ver_fila():
    resp = enviar({"op": 4})
    fila = resp.get("fila", [])
    if not fila:
        print("  Fila de reservas vazia.")
        return
    print(f"\n  {len(fila)} reserva(s) na fila:")
    for i, r in enumerate(fila, 1):
        print(f"  {i}o - usuario {r['usuario_id']} aguardando livro {r['livro_id']}")


def menu_interativo():
    print("==========================================")
    print("   BIBLIOTECA - CLIENTE")
    print(f"   SERVIDOR: {SERVIDOR_HOST}:{SERVIDOR_PORT}")
    print("==========================================")
    while True:
        print("\n 1. Ver livros disponiveis")
        print(" 2. Alugar livro")
        print(" 3. Devolver livro")
        print(" 4. Ver fila de reservas")
        print(" 0. Sair")
        op = input(" Escolha: ").strip()
        if op == "1":
            listar_livros()
        elif op == "2":
            alugar_livro()
        elif op == "3":
            devolver_livro()
        elif op == "4":
            ver_fila()
        elif op == "0":
            break
        else:
            print(" Opcao invalida.")


def modo_automatico():
    """Usado pela simulacao: aluga 1 livro especifico e encerra."""
    usuario_id = int(os.environ["USUARIO_ID"])
    livro_id = int(os.environ["LIVRO_ID"])
    time.sleep(0.05)  # pequena variacao para nao bater tudo no mesmo milissegundo
    resp = enviar({"op": 2, "usuario_id": usuario_id, "livro_id": livro_id})
    if resp["ok"]:
        print(f"[USUARIO {usuario_id}] CONFIRMADO: {resp['msg']}")
    else:
        print(f"[USUARIO {usuario_id}] RECUSADO: {resp['msg']}")
    sys.exit(0)


if __name__ == "__main__":
    if os.environ.get("MODO_AUTO") == "1":
        modo_automatico()
    else:
        menu_interativo()