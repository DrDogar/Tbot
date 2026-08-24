from config.settings import CHUNK_SIZE_USD, MAX_POSITION_CHUNKS, MIN_POSITION_CHUNKS


def size_position(confidence):
    chunks = round(confidence * MAX_POSITION_CHUNKS)
    chunks = max(MIN_POSITION_CHUNKS, min(chunks, MAX_POSITION_CHUNKS))

    return chunks * CHUNK_SIZE_USD
