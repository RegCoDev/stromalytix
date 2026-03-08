"""Test that CC3D knowledge base is embedded in ChromaDB."""

from core.rag import load_vectorstore


def test_cc3d_kb_embedded():
    """Verify ChromaDB vectorstore has >3500 chunks after CC3D embedding."""
    db = load_vectorstore()
    count = db._collection.count()
    assert count > 3500, f"Expected >3500 chunks, got {count}"
