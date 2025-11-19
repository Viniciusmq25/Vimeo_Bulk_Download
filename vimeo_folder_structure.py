"""Imprime a estrutura de pastas e vídeos da conta do Vimeo.

Requisitos:
	pip install requests

Exemplo de uso:
	python vimeo_estrutura_pastas.py --token "seu_token_vimeo_aqui"

O token pode ser gerado em https://developer.vimeo.com/apps com escopos
"public", "private" e "video_files". Se a variável de ambiente
VIMEO_TOKEN estiver definida, o argumento --token é opcional.

ATENÇÃO: NUNCA compartilhe ou commite seu token no Git!
Use .env ou variáveis de ambiente para armazená-lo com segurança.

Exemplos:
	# Usando variável de ambiente:
	export VIMEO_TOKEN="seu_token_vimeo_aqui"
	python vimeo_folder_structure.py
	
	# Usando --token (apenas para testes, não recomendado):
	python vimeo_folder_structure.py --token "seu_token_vimeo_aqui" --folders-only
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from requests import exceptions as req_exc

API = "https://api.vimeo.com"
PAGE_SIZE = 100


class VimeoError(Exception):
	"""Erro de alto nível ao comunicar com a API do Vimeo."""


def bearer_headers(token: str) -> Dict[str, str]:
	return {
		"Authorization": f"bearer {token}",
		"Accept": "application/vnd.vimeo.*+json;version=3.4",
		"User-Agent": "vimeo-folder-structure/1.0",
	}


def api_get(
	url: str,
	headers: Dict[str, str],
	params: Optional[Dict[str, str]] = None,
	max_attempts: int = 5,
) -> Dict:
	for attempt in range(1, max_attempts + 1):
		try:
			response = requests.get(url, headers=headers, params=params, timeout=60)
		except req_exc.RequestException as exc:
			if attempt == max_attempts:
				raise VimeoError(f"Erro de rede ao chamar {url}: {exc}") from exc
			time.sleep(attempt * 2)
			continue

		if response.status_code == 429:
			wait_for = int(response.headers.get("Retry-After", "5"))
			time.sleep(max(wait_for, 1))
			continue

		if response.status_code == 401:
			raise VimeoError("Token inválido ou sem permissões suficientes.")

		if response.status_code >= 400:
			raise VimeoError(
				f"Erro {response.status_code} ao chamar {url}: {response.text.strip()}"
			)

		try:
			return response.json()
		except ValueError as exc:
			raise VimeoError("Resposta inesperada da API (JSON inválido).") from exc

	raise VimeoError("Falha ao obter resposta válida da API do Vimeo.")


def paginate(
	url: str,
	headers: Dict[str, str],
	query: Optional[Dict[str, str]] = None,
) -> Iterable[Dict]:
	params = {"per_page": str(PAGE_SIZE)}
	if query:
		params.update(query)

	next_url: Optional[str] = url
	next_params: Optional[Dict[str, str]] = params

	while next_url:
		data = api_get(next_url, headers, params=next_params)
		for item in data.get("data", []):
			yield item

		paging = data.get("paging") or {}
		next_link = paging.get("next")
		if not next_link:
			break
		if next_link.startswith("http"):
			next_url = next_link
		else:
			next_url = f"{API}{next_link}"
		next_params = None


def montar_mapa_pastas(headers: Dict[str, str]) -> Dict[Optional[str], List[Dict]]:
	todos = list(
		paginate(
			f"{API}/me/projects",
			headers,
			query={
				"fields": (
					"uri,name,"
					"metadata.connections.parent_folder.uri,"
					"metadata.connections.parent_folder.name"
				)
			},
		)
	)

	mapa: Dict[Optional[str], List[Dict]] = {}
	for folder in todos:
		folder_id = extrair_id(folder.get("uri"))
		folder["_id"] = folder_id

		connections = folder.get("metadata", {}).get("connections")
		if not connections:
			parent_info = {}
		elif isinstance(connections, list):
			parent_info = connections[0].get("parent_folder", {}) if connections else {}
		else:
			parent_info = connections.get("parent_folder", {})

		if isinstance(parent_info, list):
			parent_info = parent_info[0] if parent_info else {}

		parent_uri = parent_info.get("uri") if isinstance(parent_info, dict) else None
		parent_id = extrair_id(parent_uri) if parent_uri else None
		folder["_parent_id"] = parent_id

		mapa.setdefault(parent_id, []).append(folder)

	mapa.setdefault(None, [])
	return mapa


def listar_videos_da_pasta(folder_uri: str, headers: Dict[str, str]) -> List[Dict]:
	return list(
		paginate(
			f"{API}{folder_uri}/videos",
			headers,
			query={"fields": "uri,name"},
		)
	)


def listar_videos_sem_pasta(headers: Dict[str, str]) -> List[Dict]:
	videos: List[Dict] = []
	for video in paginate(
		f"{API}/me/videos",
		headers,
		query={"fields": "uri,name,metadata.connections.folders.total"},
	):
		folders_meta = (
			video.get("metadata", {})
			.get("connections", {})
			.get("folders", {})
		)
		total = folders_meta.get("total") or folders_meta.get("totalCount")
		if not total:
			videos.append(video)
	return videos


def obter_nome_conta(headers: Dict[str, str]) -> str:
	try:
		perfil = api_get(f"{API}/me", headers, params={"fields": "name"})
	except VimeoError:
		return "Conta Vimeo"
	nome = perfil.get("name")
	if nome:
		return f"Conta Vimeo ({nome})"
	return "Conta Vimeo"


def nome_limpo(valor: Optional[str], fallback: str) -> str:
	if not valor:
		return fallback
	return " ".join(valor.split())


def extrair_id(uri: Optional[str]) -> str:
	if not uri:
		return "?"
	return uri.rstrip("/").split("/")[-1]


def ordenar_por_nome(itens: Sequence[Dict]) -> List[Dict]:
	return sorted(itens, key=lambda item: nome_limpo(item.get("name"), "").lower())


def imprimir_grupo_videos(
	videos: List[Dict],
	prefixo: str,
) -> None:
	for indice, video in enumerate(videos):
		ultimo = indice == len(videos) - 1
		conector = "`-- " if ultimo else "|-- "
		titulo = nome_limpo(video.get("name"), f"video {extrair_id(video.get('uri'))}")
		vid = extrair_id(video.get("uri"))
		print(f"{prefixo}{conector}{titulo} [video {vid}]")


def imprimir_pasta(
	pasta: Dict,
	prefixo: str,
	mapa: Dict[Optional[str], List[Dict]],
	headers: Dict[str, str],
	incluir_videos: bool,
	visitados: set[str],
) -> None:
	uri = pasta.get("uri")
	if not uri or uri in visitados:
		return
	visitados.add(uri)

	folder_id = pasta.get("_id")
	subpastas = ordenar_por_nome(mapa.get(folder_id, []))
	itens: List[Tuple[str, object]] = [("pasta", item) for item in subpastas]

	videos: List[Dict] = []
	if incluir_videos:
		videos = listar_videos_da_pasta(uri, headers)
		for video in videos:
			itens.append(("video", video))

	for indice, (tipo, conteudo) in enumerate(itens):
		ultimo = indice == len(itens) - 1
		conector = "`-- " if ultimo else "|-- "
		proximo_prefixo = prefixo + ("    " if ultimo else "|   ")

		if tipo == "pasta":
			nome = nome_limpo(
				conteudo.get("name"),
				f"pasta {extrair_id(conteudo.get('uri'))}",
			)
			pid = extrair_id(conteudo.get("uri"))
			print(f"{prefixo}{conector}{nome} [pasta {pid}]")
			imprimir_pasta(
				conteudo,
				proximo_prefixo,
				mapa,
				headers,
				incluir_videos,
				visitados,
			)
		else:
			titulo = nome_limpo(
				conteudo.get("name"),
				f"video {extrair_id(conteudo.get('uri'))}",
			)
			vid = extrair_id(conteudo.get("uri"))
			print(f"{prefixo}{conector}{titulo} [video {vid}]")


def imprimir_estrutura(
	headers: Dict[str, str],
	incluir_videos: bool,
) -> None:
	mapa = montar_mapa_pastas(headers)
	topo = ordenar_por_nome(mapa.get(None, []))
	raiz = obter_nome_conta(headers)
	print(raiz)

	itens_topo: List[Tuple[str, object]] = [("pasta", pasta) for pasta in topo]

	videos_sem_pasta: List[Dict] = []
	if incluir_videos:
		videos_sem_pasta = listar_videos_sem_pasta(headers)
		if videos_sem_pasta:
			itens_topo.append(("sem_pasta", videos_sem_pasta))

	visitados: set[str] = set()

	for indice, (tipo, conteudo) in enumerate(itens_topo):
		ultimo = indice == len(itens_topo) - 1
		conector = "`-- " if ultimo else "|-- "
		prefixo = ""
		proximo_prefixo = "    " if ultimo else "|   "

		if tipo == "pasta":
			nome = nome_limpo(
				conteudo.get("name"),
				f"pasta {extrair_id(conteudo.get('uri'))}",
			)
			pid = extrair_id(conteudo.get("uri"))
			print(f"{conector}{nome} [pasta {pid}]")
			imprimir_pasta(
				conteudo,
				proximo_prefixo,
				mapa,
				headers,
				incluir_videos,
				visitados,
			)
		else:
			print(f"{conector}Sem pasta")
			imprimir_grupo_videos(conteudo, proximo_prefixo)


def criar_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Imprime a árvore de pastas e vídeos da conta do Vimeo.",
	)
	parser.add_argument(
		"--token",
		type=str,
		default=os.environ.get("VIMEO_TOKEN"),
		help="Token pessoal do Vimeo (escopos public, private, video_files).",
	)
	parser.add_argument(
		"--folders-only",
		action="store_true",
		help="Não listar vídeos, apenas a hierarquia de pastas.",
	)
	return parser


def main() -> None:
	parser = criar_parser()
	args = parser.parse_args()
	if not args.token:
		parser.error("Informe --token ou defina a variável de ambiente VIMEO_TOKEN.")

	headers = bearer_headers(args.token)
	try:
		imprimir_estrutura(headers, incluir_videos=not args.folders_only)
	except VimeoError as exc:
		print(f"Erro: {exc}", file=sys.stderr)
		sys.exit(1)


if __name__ == "__main__":
	main()
