#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.database import get_db
from app.engines.classification.engine import ClassificationEngine
from sqlalchemy import text

async def check_noise_filter():
    async for db in get_db():
        engine = ClassificationEngine(db)
        
        query = text('''
            SELECT 
                hts_code,
                tariff_text_short,
                tariff_text
            FROM hts_versions
            WHERE hts_code = '8518301000'
        ''')
        result = await db.execute(query)
        row = result.first()
        
        if row:
            combined_text = f"{row[1] or ''} {row[2] or ''}".strip()
            print('HTS 8518301000 text:')
            print(combined_text[:200])
            print()
            
            is_noisy = engine._is_noisy_description(combined_text)
            status = "REMOVED" if is_noisy else "KEPT"
            print(f'Noise filter result: {status}')
            print()
            
            tokens = [t for t in combined_text.split() if len(t) >= 2]
            total_chars = len(combined_text)
            digits = sum(1 for c in combined_text if c.isdigit())
            letters = sum(1 for c in combined_text if c.isalpha())
            punctuation = sum(1 for c in combined_text if c in '.,;:!?()[]{}"\'-')
            
            print('Analysis:')
            print(f'  Tokens (>=2 chars): {len(tokens)}')
            print(f'  Total chars: {total_chars}')
            if total_chars > 0:
                print(f'  Digits: {digits} ({digits/total_chars*100:.1f}%)')
                print(f'  Letters: {letters} ({letters/total_chars*100:.1f}%)')
                print(f'  Punctuation: {punctuation} ({punctuation/total_chars*100:.1f}%)')
        
        break

if __name__ == "__main__":
    asyncio.run(check_noise_filter())
