"""
simular.py — Simulacao distribuida com containers Docker reais
Cada usuario simulado sobe em 1 container proprio, com IP independente.
Equivalente ao simular.ps1 do projeto de Controle de Estoque.

Modos:
  1) Mesmo livro    — N usuarios disputando o MESMO livro (mostra concorrencia/mutex)
  2) Livros diferentes — voce escolhe usuario+livro manualmente para cada container

Uso: python simular.py
"""

import subprocess
import time
import sys
import pickle
import socket
import os

COMPOSE = ["docker", "compose"]
SERVIDOR_HOST = os.environ.get("SERVIDOR_HOST", "127.0.0.1")
SERVIDOR_PORT = int(os.environ.get("SERVIDOR_PORT", "8086"))


def run(cmd, capture=True):
    r = subprocess.run(cmd, capture_output=capture, text=True)
    return r.stdout.strip() if capture else None


def servidor_rodando():
    out = run(COMPOSE + ["ps", "-q", "servidor-biblioteca"])
    return bool(out)


def garantir_servidor():
    if servidor_rodando():
        return
    print(" Servidor nao esta rodando. Subindo...")
    run(COMPOSE + ["up", "-d", "--build", "servidor-biblioteca"], capture=False)
    for _ in range(10):
        time.sleep(1)
        if servidor_rodando():
            print(" Servidor pronto.")
            return
    print(" ERRO: servidor nao subiu. Execute manualmente: docker compose up --build")
    sys.exit(1)


def consultar(op, extra=None):
    """Consulta direta ao servidor (fora do Docker, via porta exposta) so para listar."""
    req = {"op": op, "origem": "simulador"}
    if extra:
        req.update(extra)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((SERVIDOR_HOST, SERVIDOR_PORT))
            s.sendall(pickle.dumps(req) + b"\n")
            dados = b""
            while not dados.endswith(b"\n"):
                parte = s.recv(4096)
                if not parte:
                    break
                dados += parte
            return pickle.loads(dados.rstrip(b"\n"))
    except Exception as e:
        print(f" Aviso: nao foi possivel consultar o servidor diretamente ({e}).")
        print(" Isso e' normal se a porta 8086 nao estiver exposta no host —")
        print(" use o cliente/admin para ver livros e usuarios antes de simular.")
        return None


def mostrar_livros():
    resp = consultar(0)
    if not resp:
        return []
    livros = resp.get("livros", [])
    print("\n  ID  TITULO                          STATUS")
    print("  " + "-" * 55)
    for l in livros:
        status = "Disponivel" if l["status"] == "disponivel" else "Emprestado"
        print(f"  {l['id']:<4}{l['titulo'][:30]:<32}{status}")
    return livros


def mostrar_usuarios():
    resp = consultar(20)
    if not resp:
        return []
    usuarios = resp.get("usuarios", [])
    print("\n  ID  NOME")
    print("  " + "-" * 30)
    for u in usuarios:
        print(f"  {u['id']:<4}{u['nome']}")
    return usuarios


def subir_container(usuario_id, livro_id):
    cid = run(COMPOSE + [
        "run", "-d", "--no-deps",
        "-e", "MODO_AUTO=1",
        "-e", f"USUARIO_ID={usuario_id}",
        "-e", f"LIVRO_ID={livro_id}",
        "cliente-biblioteca",
    ])
    return cid


def validar_usuarios_existem(usuarios_pedidos, usuarios_cadastrados):
    """Verifica se todos os IDs de usuario pedidos realmente existem. Retorna (ok, faltantes)."""
    ids_existentes = {u["id"] for u in usuarios_cadastrados}
    faltantes = [uid for uid in usuarios_pedidos if uid not in ids_existentes]
    return (len(faltantes) == 0, faltantes)


def validar_quantidade_usuarios(n_pedido, usuarios_cadastrados):
    """Verifica se ha usuarios cadastrados suficientes para a quantidade pedida."""
    n_disponivel = len(usuarios_cadastrados)
    if n_pedido > n_disponivel:
        print(f"\n ERRO: voce pediu {n_pedido} usuario(s), mas so ha {n_disponivel} cadastrado(s).")
        print(" Cadastre mais usuarios pelo admin (opcao 3) e tente novamente.")
        return False
    return True


def coletar_resultado(pares_usuario_container):
    print("\n Aguardando resultado...\n")
    time.sleep(2)
    confirmados = 0
    recusados = 0
    for usuario_id, livro_id, cid in pares_usuario_container:
        log = run(["docker", "logs", cid])
        if "CONFIRMADO" in log:
            confirmados += 1
            print(f"  Usuario {usuario_id} (livro {livro_id}) -> CONFIRMADO")
        elif "RECUSADO" in log:
            recusados += 1
            print(f"  Usuario {usuario_id} (livro {livro_id}) -> RECUSADO")
        else:
            print(f"  Usuario {usuario_id} (livro {livro_id}) -> SEM RESPOSTA (ainda processando)")
    return confirmados, recusados


def modo_mesmo_livro():
    print("\n  --- Modo: N usuarios disputando o MESMO livro ---")
    print("  Demonstra concorrencia: mutex garantindo exclusao mutua.")

    mostrar_livros()
    usuarios = mostrar_usuarios()

    try:
        n_usuarios = int(input("\n Quantos usuarios vao disputar o mesmo livro? "))
        livro_id = int(input(" ID do livro a disputar: "))
        primeiro_usuario_id = int(input(" ID do primeiro usuario (os demais serao sequenciais): "))
    except ValueError:
        print(" Valor invalido.")
        return

    if not validar_quantidade_usuarios(n_usuarios, usuarios):
        return

    ids_pedidos = [primeiro_usuario_id + i for i in range(n_usuarios)]
    ok, faltantes = validar_usuarios_existem(ids_pedidos, usuarios)
    if not ok:
        print(f"\n ERRO: os seguintes IDs de usuario nao existem: {faltantes}")
        print(" Verifique a lista de usuarios cadastrados acima e tente novamente.")
        return

    print(f"\n Subindo {n_usuarios} container(s), cada um e' um usuario tentando o livro {livro_id}.\n")

    pares = []
    for i in range(n_usuarios):
        usuario_id = primeiro_usuario_id + i
        cid = subir_container(usuario_id, livro_id)
        pares.append((usuario_id, livro_id, cid))
        print(f"  Usuario {usuario_id} -> container {cid[:12]}")

    confirmados, recusados = coletar_resultado(pares)

    print("\n==========================================")
    print("   RESULTADO — MESMO LIVRO")
    print("==========================================")
    print(f"  Usuarios disputando : {n_usuarios}")
    print(f"  Confirmados         : {confirmados}  (esperado: 1)")
    print(f"  Recusados           : {recusados}  (esperado: {n_usuarios - 1})")
    print("==========================================")


def modo_livros_diferentes():
    print("\n  --- Modo: usuarios alugando livros DIFERENTES ---")
    print("  Demonstra paralelismo: varios containers atendidos ao mesmo tempo.")

    livros = mostrar_livros()
    usuarios = mostrar_usuarios()

    print("\n Como configurar usuario x livro?")
    print(" 1. Geral — informo a quantidade e o sistema distribui automaticamente")
    print(" 2. Individual — eu escolho usuario e livro um por um")
    sub = input(" Escolha: ").strip()

    if sub == "1":
        pares_entrada = _config_geral(livros, usuarios)
    elif sub == "2":
        pares_entrada = _config_individual(usuarios)
    else:
        print(" Opcao invalida.")
        return

    if not pares_entrada:
        return

    n_usuarios = len(pares_entrada)
    print(f"\n Subindo {n_usuarios} container(s), cada um alugando um livro diferente.\n")

    pares = []
    for usuario_id, livro_id in pares_entrada:
        cid = subir_container(usuario_id, livro_id)
        pares.append((usuario_id, livro_id, cid))
        print(f"  Usuario {usuario_id} (livro {livro_id}) -> container {cid[:12]}")

    confirmados, recusados = coletar_resultado(pares)

    print("\n==========================================")
    print("   RESULTADO — LIVROS DIFERENTES")
    print("==========================================")
    print(f"  Usuarios            : {n_usuarios}")
    print(f"  Confirmados         : {confirmados}")
    print(f"  Recusados           : {recusados}")
    print("==========================================")


def _config_geral(livros, usuarios):
    """Distribui automaticamente: usuario[0]->livro[0], usuario[1]->livro[1], etc. (round-robin)."""
    try:
        n_usuarios = int(input("\n Quantos usuarios vao participar? "))
        primeiro_usuario_id = int(input(" ID do primeiro usuario (os demais serao sequenciais): "))
        primeiro_livro_id = int(input(" ID do primeiro livro (os demais serao sequenciais): "))
    except ValueError:
        print(" Valor invalido.")
        return []

    if not validar_quantidade_usuarios(n_usuarios, usuarios):
        return []

    ids_usuarios_pedidos = [primeiro_usuario_id + i for i in range(n_usuarios)]
    ok, faltantes = validar_usuarios_existem(ids_usuarios_pedidos, usuarios)
    if not ok:
        print(f"\n ERRO: os seguintes IDs de usuario nao existem: {faltantes}")
        print(" Verifique a lista de usuarios cadastrados acima e tente novamente.")
        return []

    ids_livros_existentes = {l["id"] for l in livros}
    ids_livros_pedidos = [primeiro_livro_id + i for i in range(n_usuarios)]
    faltantes_livros = [lid for lid in ids_livros_pedidos if lid not in ids_livros_existentes]
    if faltantes_livros:
        print(f"\n ERRO: os seguintes IDs de livro nao existem: {faltantes_livros}")
        print(" Verifique a lista de livros cadastrados acima e tente novamente.")
        return []

    pares = list(zip(ids_usuarios_pedidos, ids_livros_pedidos))
    print("\n Distribuicao automatica gerada:")
    for uid, lid in pares:
        print(f"   usuario {uid} -> livro {lid}")
    return pares


def _config_individual(usuarios):
    """Pede usuario+livro um por um, manualmente."""
    try:
        n_usuarios = int(input("\n Quantos usuarios vao participar? "))
    except ValueError:
        print(" Valor invalido.")
        return []

    if not validar_quantidade_usuarios(n_usuarios, usuarios):
        return []

    ids_existentes = {u["id"] for u in usuarios}

    pares = []
    for i in range(1, n_usuarios + 1):
        print(f"\n  -- Usuario #{i} --")
        try:
            uid = int(input(f"  ID do usuario #{i}: "))
            lid = int(input(f"  ID do livro para usuario #{i}: "))
        except ValueError:
            print(" Valor invalido. Abortando.")
            return []
        if uid not in ids_existentes:
            print(f" ERRO: usuario_id={uid} nao existe na lista de usuarios cadastrados. Abortando.")
            return []
        pares.append((uid, lid))
    return pares


def main():
    print("==========================================")
    print("   SIMULACAO DISTRIBUIDA - BIBLIOTECA")
    print("==========================================")

    garantir_servidor()

    print("\n Escolha o modo de simulacao:")
    print(" 1. Varios usuarios disputando o MESMO livro (concorrencia)")
    print(" 2. Cada usuario aluga um livro DIFERENTE (paralelismo)")
    modo = input(" Escolha: ").strip()

    if modo == "1":
        modo_mesmo_livro()
    elif modo == "2":
        modo_livros_diferentes()
    else:
        print(" Opcao invalida.")
        return

    print("\n Containers ficam ativos para inspecao (docker ps / docker logs <id>).")


if __name__ == "__main__":
    main()