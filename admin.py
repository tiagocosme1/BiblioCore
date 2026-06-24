"""
admin.py — Painel administrativo da biblioteca
CRUD de livros e usuarios via socket TCP. Mesmo padrao do admin.c.
"""

import socket
import pickle
import os

SERVIDOR_HOST = os.environ.get("SERVIDOR_HOST", "127.0.0.1")
SERVIDOR_PORT = int(os.environ.get("SERVIDOR_PORT", "8086"))


def enviar(req):
    req["origem"] = "admin"
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
    resp = enviar({"op": 10})
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
    resp = enviar({"op": 17})
    usuarios = resp.get("usuarios", [])
    print("\n  ID  NOME")
    print("  " + "-" * 30)
    for u in usuarios:
        print(f"  {u['id']:<4}{u['nome']}")
    if not usuarios:
        print("  (nenhum usuario cadastrado)")
    return usuarios


def cadastrar_livro():
    titulo = input("  Titulo: ").strip()
    if not titulo:
        print("  Titulo invalido.")
        return
    autor = input("  Autor: ").strip()
    resp = enviar({"op": 11, "titulo": titulo, "autor": autor})
    print(f"  {'OK' if resp['ok'] else 'ERRO'}: {resp['msg']}")


def excluir_livro():
    listar_livros()
    try:
        lid = int(input("\n  ID do livro a excluir: "))
    except ValueError:
        print("  ID invalido.")
        return
    resp = enviar({"op": 12, "livro_id": lid})
    print(f"  {'OK' if resp['ok'] else 'ERRO'}: {resp['msg']}")


def cadastrar_usuario():
    nome = input("  Nome: ").strip()
    if not nome:
        print("  Nome invalido.")
        return
    resp = enviar({"op": 13, "nome": nome})
    print(f"  {'OK' if resp['ok'] else 'ERRO'}: {resp['msg']}")


def excluir_usuario():
    listar_usuarios()
    try:
        uid = int(input("\n  ID do usuario a excluir: "))
    except ValueError:
        print("  ID invalido.")
        return
    resp = enviar({"op": 14, "usuario_id": uid})
    print(f"  {'OK' if resp['ok'] else 'ERRO'}: {resp['msg']}")


def listar_emprestimos():
    resp = enviar({"op": 15})
    emps = resp.get("emprestimos", [])
    if not emps:
        print("  (nenhum emprestimo ativo)")
        return
    print(f"\n  {'ID':<5}{'USUARIO':<22}{'LIVRO':<32}DATA")
    print("  " + "-" * 75)
    for e in emps:
        print(f"  {e['id']:<5}{e['usuario'][:20]:<22}{e['livro'][:30]:<32}{e['data']}")


def ver_fila():
    resp = enviar({"op": 16})
    fila = resp.get("fila", [])
    if not fila:
        print("  Fila de reservas vazia.")
        return
    print(f"\n  {len(fila)} reserva(s) na fila:")
    for i, r in enumerate(fila, 1):
        print(f"  {i}o - usuario {r['usuario_id']} aguardando livro {r['livro_id']}")


def menu():
    print("==========================================")
    print("   BIBLIOTECA - PAINEL ADMIN")
    print(f"   SERVIDOR: {SERVIDOR_HOST}:{SERVIDOR_PORT}")
    print("==========================================")
    while True:
        print("\n 1. Cadastrar livro")
        print(" 2. Excluir livro")
        print(" 3. Cadastrar usuario")
        print(" 4. Excluir usuario")
        print(" 5. Listar livros")
        print(" 6. Listar usuarios")
        print(" 7. Listar emprestimos ativos")
        print(" 8. Ver fila de reservas")
        print(" 0. Sair")
        op = input(" Escolha: ").strip()
        if op == "1":
            cadastrar_livro()
        elif op == "2":
            excluir_livro()
        elif op == "3":
            cadastrar_usuario()
        elif op == "4":
            excluir_usuario()
        elif op == "5":
            listar_livros()
        elif op == "6":
            listar_usuarios()
        elif op == "7":
            listar_emprestimos()
        elif op == "8":
            ver_fila()
        elif op == "0":
            break
        else:
            print(" Opcao invalida.")


if __name__ == "__main__":
    menu()