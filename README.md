# Library Management System (Python)

Sistema de gerenciamento de biblioteca desenvolvido em **Python** para controle de livros, usuários e empréstimos.

Projeto desenvolvido para a disciplina **Projeto Integrador de Computação Paralela** do curso de **Sistemas de Informação**.

## 📚 Funcionalidades

O sistema permite:

* Cadastro de livros
* Listagem de livros
* Remoção de livros
* Cadastro de usuários
* Listagem de usuários
* Remoção de usuários
* Empréstimo de livros
* Devolução de livros
* Histórico de operações
* Controle de disponibilidade de livros

## 🧠 Estruturas de Dados Utilizadas

O projeto utiliza algumas estruturas clássicas da computação:

* **Fila (Queue)**
  Utilizada para organizar reservas de livros.

* **Pilha (Stack)**
  Utilizada para registrar histórico de operações.

## 💾 Persistência de Dados

Os dados são armazenados localmente em arquivo:

```
database.json
```

Isso permite que as informações permaneçam salvas mesmo após o programa ser fechado.

## 🖥️ Interface

O sistema funciona via **CLI (Command Line Interface)**, utilizando o terminal para interação com o usuário.

Exemplo de menu:

```
===== SISTEMA BIBLIOTECA =====

1 - Cadastrar livro
2 - Listar livros
3 - Excluir livro
4 - Cadastrar usuário
5 - Listar usuários
6 - Excluir usuário
7 - Emprestar livro
8 - Devolver livro
9 - Sair
```

## ⚙️ Tecnologias Utilizadas

* Python 3
* Estruturas de dados (Fila e Pilha)
* Manipulação de arquivos JSON

## 📂 Estrutura do Projeto

```
Library-Management-Python
│
├── main.py
├── models.py
├── storage.py
├── queue_stack.py
└── database.json
```

## ▶️ Como Executar

1. Clone o repositório

```
git clone https://github.com/tiagocosme1/Library-Management-Python.git
```

2. Acesse a pasta

```
cd Library-Management-Python
```

3. Execute o programa

```
python main.py
```

5.Funcionalidades

- Implementadas
  *Python.
  *SQL.
  *Pilha e Fila.
- Em desenvolvimento
  *Cliente com interface gráfica.
- Planejadas
  *Arquitetura Cliente-Servidor.
  *Cliente com interface gráfica.
  *Servidor responsável por regras de negócio.
  *Comunicação via sockets TCP.
  *Uso futuro de banco de dados (SQLite ou PostgreSQL).
  *Implementação de API para expansão.
  *Possível uso de threads para concorrência.


## 👨‍💻 Autores

Projeto desenvolvido por:

* Tiago Geraldo de Lima Cosme
* Waldo Andrade Silva
* Álex de Almeida Santana
