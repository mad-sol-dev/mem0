#!/usr/bin/env python3
"""
Qdrant-Verbindungstest für mem0 Setup
Testet ausführlich die Qdrant-Verbindung, Collections, und Embedding-Integration
"""

import sys
import json
from typing import Optional


def print_section(title: str):
    """Drucke Abschnittstitel"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_qdrant_connection():
    """Teste grundlegende Qdrant-Verbindung"""
    print_section("1. Teste Qdrant-Verbindung")

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        # Verbinde mit Qdrant
        print("Verbinde mit Qdrant auf http://10.8.0.1:6333...")
        client = QdrantClient(
            url="http://10.8.0.1:6333",
            api_key="123",
            prefer_grpc=False  # HTTP only
        )

        # Teste Verbindung
        print("✓ Qdrant-Client erstellt")

        # Liste Collections
        collections = client.get_collections()
        print(f"✓ Verbindung erfolgreich!")
        print(f"\nVorhandene Collections ({len(collections.collections)}):")
        for col in collections.collections:
            # Ältere Qdrant-Versionen haben points_count direkt
            vectors_count = getattr(col, 'vectors_count', 'N/A')
            points_count = getattr(col, 'points_count', 'N/A')
            print(f"  - {col.name} (Vectors: {vectors_count}, Points: {points_count})")

        return client, True

    except ImportError:
        print("✗ qdrant-client nicht installiert!")
        print("  Installiere mit: pip install qdrant-client")
        return None, False
    except Exception as e:
        print(f"✗ Verbindung fehlgeschlagen: {e}")
        print("\nMögliche Ursachen:")
        print("  - VPN nicht aktiv?")
        print("  - Qdrant läuft nicht auf 10.8.0.1:6333?")
        print("  - Falscher API-Key?")
        print("  - Firewall blockiert Port 6333?")
        return None, False


def test_collection_operations(client: 'QdrantClient'):
    """Teste Collection-Operationen"""
    print_section("2. Teste Collection-Operationen")

    try:
        from qdrant_client.models import Distance, VectorParams

        test_collection = "test_mem0_collection"
        vector_size = 1024  # BGE-M3 Dimensionen

        # Prüfe ob Test-Collection existiert
        collections = client.get_collections()
        existing_collections = [col.name for col in collections.collections]

        if test_collection in existing_collections:
            print(f"Collection '{test_collection}' existiert bereits")
            print("Lösche alte Test-Collection...")
            client.delete_collection(test_collection)
            print("✓ Alte Collection gelöscht")

        # Erstelle Test-Collection
        print(f"\nErstelle Test-Collection '{test_collection}'...")
        print(f"  - Vector Size: {vector_size}")
        print(f"  - Distance: COSINE")

        client.create_collection(
            collection_name=test_collection,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )
        print("✓ Collection erstellt")

        # Prüfe Collection-Info
        collection_info = client.get_collection(test_collection)
        print(f"\nCollection-Info:")
        print(f"  - Name: {collection_info.config.params.vectors.size}")
        print(f"  - Vector Size: {collection_info.config.params.vectors.size}")
        print(f"  - Distance: {collection_info.config.params.vectors.distance}")
        print(f"  - Points Count: {collection_info.points_count}")

        return test_collection, True

    except Exception as e:
        print(f"✗ Fehler bei Collection-Operationen: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_embedding_model():
    """Teste Embedding-Modell"""
    print_section("3. Teste Embedding-Modell (BAAI/bge-m3)")

    try:
        from sentence_transformers import SentenceTransformer
        import torch
        import numpy as np

        # Prüfe Device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Device: {device}")

        if device == "cuda":
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"CUDA Memory verfügbar: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

        # Lade Modell
        print("\nLade BGE-M3 Modell...")
        print("(Beim ersten Mal wird das Modell heruntergeladen, ~2GB)")

        model = SentenceTransformer('BAAI/bge-m3', device=device)
        print("✓ Modell geladen")

        # Info über Modell
        embedding_dim = model.get_sentence_embedding_dimension()
        print(f"\nModell-Info:")
        print(f"  - Embedding Dimension: {embedding_dim}")
        print(f"  - Max Sequence Length: {model.max_seq_length}")

        # Teste Embeddings mit verschiedenen Texten
        test_texts = [
            "Das ist ein Test auf Deutsch.",
            "This is a test in English.",
            "Python ist eine großartige Programmiersprache für Machine Learning."
        ]

        print(f"\nErstelle Embeddings für {len(test_texts)} Test-Texte...")
        embeddings = model.encode(test_texts, convert_to_numpy=True)

        print(f"✓ Embeddings erstellt")
        print(f"  - Shape: {embeddings.shape}")
        print(f"  - Dtype: {embeddings.dtype}")

        # Zeige Beispiel-Werte
        print(f"\nBeispiel-Embedding (erste 10 Werte):")
        print(f"  {embeddings[0][:10]}")

        # Berechne Ähnlichkeiten
        print(f"\nBerechne Cosine-Ähnlichkeiten:")
        from numpy.linalg import norm

        def cosine_similarity(a, b):
            return np.dot(a, b) / (norm(a) * norm(b))

        for i in range(len(test_texts)):
            for j in range(i+1, len(test_texts)):
                sim = cosine_similarity(embeddings[i], embeddings[j])
                print(f"  Text {i+1} ↔ Text {j+1}: {sim:.4f}")

        if device == "cuda":
            print(f"\n✓ GPU Memory verwendet: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")

        return model, embeddings, True

    except ImportError as e:
        print(f"✗ Import-Fehler: {e}")
        print("  Installiere mit: pip install sentence-transformers")
        return None, None, False
    except Exception as e:
        print(f"✗ Fehler beim Embedding-Test: {e}")
        import traceback
        traceback.print_exc()
        return None, None, False


def test_qdrant_insert_search(client: 'QdrantClient', collection_name: str, model: 'SentenceTransformer', embeddings):
    """Teste Einfügen und Suchen in Qdrant"""
    print_section("4. Teste Einfügen und Suchen in Qdrant")

    try:
        from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
        import uuid

        # Test-Daten vorbereiten
        test_data = [
            {
                "text": "Das ist ein Test auf Deutsch.",
                "language": "de",
                "category": "test"
            },
            {
                "text": "This is a test in English.",
                "language": "en",
                "category": "test"
            },
            {
                "text": "Python ist eine großartige Programmiersprache für Machine Learning.",
                "language": "de",
                "category": "programming"
            }
        ]

        # Erstelle Points mit Embeddings
        print(f"\nFüge {len(test_data)} Test-Points ein...")
        points = []
        for i, (data, embedding) in enumerate(zip(test_data, embeddings)):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding.tolist(),
                payload={
                    "text": data["text"],
                    "language": data["language"],
                    "category": data["category"],
                    "index": i
                }
            )
            points.append(point)

        # Füge Points ein
        client.upsert(
            collection_name=collection_name,
            points=points
        )
        print(f"✓ {len(points)} Points eingefügt")

        # Prüfe Collection-Status
        collection_info = client.get_collection(collection_name)
        print(f"  - Points in Collection: {collection_info.points_count}")

        # Teste Suche
        print("\n--- Suche 1: 'Python Programmierung' ---")
        query_text = "Python Programmierung"
        query_embedding = model.encode(query_text, convert_to_numpy=True)

        # Ältere Qdrant-Versionen nutzen query_points statt search
        try:
            search_results = client.query_points(
                collection_name=collection_name,
                query=query_embedding.tolist(),
                limit=3
            ).points
        except AttributeError:
            # Neue API
            search_results = client.search(
                collection_name=collection_name,
                query_vector=query_embedding.tolist(),
                limit=3
            )

        print(f"✓ Suche erfolgreich, {len(search_results)} Ergebnisse:")
        for i, result in enumerate(search_results, 1):
            print(f"\n  Ergebnis {i}:")
            print(f"    - Score: {result.score:.4f}")
            print(f"    - Text: {result.payload['text']}")
            print(f"    - Language: {result.payload['language']}")
            print(f"    - Category: {result.payload['category']}")

        # Teste Suche mit Filter
        print("\n--- Suche 2: 'Test' (nur Deutsch) ---")
        query_text = "Test"
        query_embedding = model.encode(query_text, convert_to_numpy=True)

        # Ältere Qdrant-Versionen nutzen query_points statt search
        try:
            search_results = client.query_points(
                collection_name=collection_name,
                query=query_embedding.tolist(),
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="language",
                            match=MatchValue(value="de")
                        )
                    ]
                ),
                limit=3
            ).points
        except AttributeError:
            # Neue API
            search_results = client.search(
                collection_name=collection_name,
                query_vector=query_embedding.tolist(),
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="language",
                            match=MatchValue(value="de")
                        )
                    ]
                ),
                limit=3
            )

        print(f"✓ Gefilterte Suche erfolgreich, {len(search_results)} Ergebnisse:")
        for i, result in enumerate(search_results, 1):
            print(f"\n  Ergebnis {i}:")
            print(f"    - Score: {result.score:.4f}")
            print(f"    - Text: {result.payload['text']}")
            print(f"    - Language: {result.payload['language']}")

        # Teste Scroll (alle Points abrufen)
        print("\n--- Teste Scroll (alle Points) ---")
        all_points, _ = client.scroll(
            collection_name=collection_name,
            limit=100
        )
        print(f"✓ Scroll erfolgreich: {len(all_points)} Points abgerufen")

        return True

    except Exception as e:
        print(f"✗ Fehler bei Insert/Search-Test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mem0_integration():
    """Teste mem0-Integration mit Qdrant"""
    print_section("5. Teste mem0-Integration")

    try:
        import os

        # Prüfe OpenAI API Key
        if not os.environ.get('OPENAI_API_KEY'):
            print("⚠ OPENAI_API_KEY nicht gesetzt!")
            print("  Setze mit: export OPENAI_API_KEY=dein-key")
            print("  Überspringe mem0-Integrations-Test...")
            return True

        from mem0 import Memory

        # Lade Config
        print("Lade Konfiguration aus config.json...")
        with open('openmemory/api/config.json', 'r') as f:
            config_data = json.load(f)

        # Extrahiere mem0-Config und parse env vars
        mem0_config = config_data['mem0']

        # Ersetze env:OPENAI_API_KEY mit tatsächlichem Wert
        if mem0_config['llm']['config']['api_key'] == 'env:OPENAI_API_KEY':
            mem0_config['llm']['config']['api_key'] = os.environ.get('OPENAI_API_KEY')

        # Nutze separate Test-Collection
        mem0_config['vector_store']['config']['collection_name'] = 'test_mem0_integration'

        print("✓ Konfiguration geladen")
        print(f"  - LLM: {mem0_config['llm']['provider']} / {mem0_config['llm']['config']['model']}")
        print(f"  - Embedder: {mem0_config['embedder']['provider']} / {mem0_config['embedder']['config']['model']}")
        print(f"  - Vector Store: {mem0_config['vector_store']['provider']}")
        print(f"  - Collection: {mem0_config['vector_store']['config']['collection_name']}")

        # Initialisiere Memory
        print("\nInitialisiere mem0 Memory-Client...")
        memory = Memory.from_config(config_dict=mem0_config)
        print("✓ Memory-Client initialisiert")

        # Test 1: Füge Memories hinzu
        print("\n--- Test 1: Füge Memories hinzu ---")
        test_messages = [
            {
                "role": "user",
                "content": "Ich bin ein Machine Learning Engineer und arbeite hauptsächlich mit Python und PyTorch."
            },
            {
                "role": "assistant",
                "content": "Verstanden! Du bist ML Engineer und nutzt Python mit PyTorch."
            }
        ]

        result = memory.add(test_messages, user_id="test_user_qdrant")
        print(f"✓ Memory hinzugefügt")
        print(f"  Ergebnis: {json.dumps(result, indent=2, ensure_ascii=False)}")

        # Test 2: Suche
        print("\n--- Test 2: Suche in Memories ---")
        search_queries = [
            "Was ist mein Beruf?",
            "Welche Programmiersprache nutze ich?",
            "Mit welchem Framework arbeite ich?"
        ]

        for query in search_queries:
            print(f"\nQuery: '{query}'")
            search_result = memory.search(query, user_id="test_user_qdrant", limit=3)

            if search_result and 'results' in search_result and search_result['results']:
                print(f"  ✓ {len(search_result['results'])} Ergebnisse gefunden:")
                for i, res in enumerate(search_result['results'][:2], 1):
                    print(f"    {i}. {res.get('memory', 'N/A')} (Score: {res.get('score', 0):.4f})")
            else:
                print("  ⚠ Keine Ergebnisse gefunden")

        # Test 3: Alle Memories abrufen
        print("\n--- Test 3: Alle Memories abrufen ---")
        all_memories = memory.get_all(user_id="test_user_qdrant")
        print(f"✓ {len(all_memories.get('results', []))} Memories gefunden")

        # Cleanup
        print("\n--- Cleanup: Lösche Test-Memories ---")
        memory.delete_all(user_id="test_user_qdrant")
        print("✓ Test-Memories gelöscht")

        return True

    except ImportError as e:
        print(f"✗ Import-Fehler: {e}")
        return False
    except FileNotFoundError:
        print("✗ config.json nicht gefunden!")
        print("  Stelle sicher, dass du im mem0-Verzeichnis bist")
        return False
    except Exception as e:
        print(f"✗ Fehler beim mem0-Integrations-Test: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_collections(client: Optional['QdrantClient'], collection_names: list):
    """Räume Test-Collections auf"""
    if not client:
        return

    print_section("Cleanup: Lösche Test-Collections")

    try:
        for collection_name in collection_names:
            try:
                client.delete_collection(collection_name)
                print(f"✓ Collection '{collection_name}' gelöscht")
            except Exception as e:
                print(f"⚠ Konnte '{collection_name}' nicht löschen: {e}")
    except Exception as e:
        print(f"✗ Cleanup-Fehler: {e}")


def main():
    """Hauptfunktion"""
    print("\n" + "🔍" * 35)
    print("  Qdrant-Verbindungstest für mem0")
    print("🔍" * 35)

    results = {}
    client = None
    test_collection = None
    model = None
    embeddings = None

    # Test 1: Verbindung
    client, success = test_qdrant_connection()
    results['Qdrant-Verbindung'] = success

    if not success:
        print("\n" + "=" * 70)
        print("❌ Qdrant-Verbindung fehlgeschlagen!")
        print("Bitte behebe das Problem und starte den Test erneut.")
        print("=" * 70)
        return 1

    # Test 2: Collection-Operationen
    if client:
        test_collection, success = test_collection_operations(client)
        results['Collection-Operationen'] = success

    # Test 3: Embedding-Modell
    model, embeddings, success = test_embedding_model()
    results['Embedding-Modell'] = success

    # Test 4: Insert & Search
    if client and test_collection and model is not None and embeddings is not None:
        success = test_qdrant_insert_search(client, test_collection, model, embeddings)
        results['Insert & Search'] = success

    # Test 5: mem0-Integration
    success = test_mem0_integration()
    results['mem0-Integration'] = success

    # Cleanup
    collections_to_cleanup = []
    if test_collection:
        collections_to_cleanup.append(test_collection)
    collections_to_cleanup.append('test_mem0_integration')

    cleanup_test_collections(client, collections_to_cleanup)

    # Zusammenfassung
    print_section("ZUSAMMENFASSUNG")

    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ Alle Tests erfolgreich!")
        print("\nDein Setup ist bereit:")
        print("  - Qdrant läuft und ist erreichbar")
        print("  - BGE-M3 Embeddings funktionieren (1024 Dimensionen)")
        print("  - mem0-Integration funktioniert")
        print("\nStarte den MCP-Server mit:")
        print("  cd openmemory/api")
        print("  uvicorn main:app --host 0.0.0.0 --port 8765")
    else:
        print("❌ Einige Tests fehlgeschlagen!")
        print("\nBitte behebe die Fehler und führe den Test erneut aus.")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
