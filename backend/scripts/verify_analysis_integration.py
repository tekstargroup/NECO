#!/usr/bin/env python3
"""
Verification Script for Analysis Integration - Sprint 12

Verifies two paths:
1. Happy path: Shipment with CI + Data Sheet -> COMPLETE analysis with ReviewRecord
2. Refusal path: Shipment with insufficient docs -> REFUSED analysis, no entitlement increment
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.database import Base
from app.models.shipment import Shipment, ShipmentStatus
from app.models.shipment_document import ShipmentDocument, ShipmentDocumentType
from app.models.analysis import Analysis, AnalysisStatus, RefusalReasonCode
from app.models.review_record import ReviewRecord
from app.models.regulatory_evaluation import RegulatoryEvaluation
from app.models.organization import Organization
from app.models.user import User
from app.models.entitlement import Entitlement
from app.services.analysis_orchestration_service import AnalysisOrchestrationService
from app.services.entitlement_service import EntitlementService

logger = logging.getLogger(__name__)


async def verify_happy_path(db: AsyncSession) -> bool:
    """
    Verify happy path: CI + Data Sheet -> COMPLETE analysis.
    
    Expected:
    - analysis.status = COMPLETE
    - review_record exists and links to shipment_id
    - regulatory_evaluations rows exist and link to review_id
    - result_json contains the 8-section data needed
    """
    print("\n=== VERIFICATION 1: Happy Path ===")
    
    try:
        # Create test org and user (or get existing)
        # For now, assume they exist - adjust as needed
        result = await db.execute(select(Organization).limit(1))
        org = result.scalar_one_or_none()
        if not org:
            print("❌ ERROR: No organization found. Please create one first.")
            return False
        
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            print("❌ ERROR: No user found. Please create one first.")
            return False
        
        # Create shipment
        shipment = Shipment(
            organization_id=org.id,
            created_by=user.id,
            name=f"Test Happy Path {datetime.utcnow().isoformat()}",
            status=ShipmentStatus.DRAFT
        )
        db.add(shipment)
        await db.flush()
        
        print(f"✓ Created shipment: {shipment.id}")
        
        # Create test documents (CI + Data Sheet)
        # NOTE: These need to exist in S3. For real verification, upload actual PDFs first.
        ci_doc = ShipmentDocument(
            shipment_id=shipment.id,
            organization_id=org.id,
            document_type=ShipmentDocumentType.COMMERCIAL_INVOICE,
            filename="test_ci.pdf",
            s3_key=f"test/{org.id}/{shipment.id}/ci.pdf",
            sha256_hash="test_ci_hash_123",
            retention_expires_at=datetime.utcnow(),
            uploaded_by=user.id
        )
        db.add(ci_doc)
        
        datasheet_doc = ShipmentDocument(
            shipment_id=shipment.id,
            organization_id=org.id,
            document_type=ShipmentDocumentType.DATA_SHEET,
            filename="test_datasheet.pdf",
            s3_key=f"test/{org.id}/{shipment.id}/datasheet.pdf",
            sha256_hash="test_datasheet_hash_456",
            retention_expires_at=datetime.utcnow(),
            uploaded_by=user.id
        )
        db.add(datasheet_doc)
        
        await db.commit()
        print(f"✓ Created documents: CI and Data Sheet")
        
        # Get initial entitlement count
        entitlement_service = EntitlementService(db)
        entitlement = await entitlement_service.get_or_create(user.id)
        initial_count = entitlement.shipments_used
        print(f"✓ Initial entitlement count: {initial_count}/15")
        
        # Run analysis
        orchestration_service = AnalysisOrchestrationService(db)
        result = await orchestration_service.start_analysis(
            shipment_id=shipment.id,
            organization_id=org.id,
            actor_user_id=user.id
        )
        
        print(f"✓ Analysis started: {result.get('analysis_id')}")
        print(f"  Status: {result.get('status')}")
        
        # Wait for analysis to complete (poll or wait)
        # NOTE: In real scenario, Celery would run this. For verification, we'd need to run it manually.
        print("  ⚠️  NOTE: Celery task must run to complete analysis.")
        print("  ⚠️  Run: celery -A app.core.celery_app worker --loglevel=info")
        print("  ⚠️  Then check analysis status via API or database.")
        
        # Check final state (after Celery completes)
        result = await db.execute(
            select(Analysis).where(Analysis.shipment_id == shipment.id).order_by(Analysis.created_at.desc())
        )
        analysis = result.scalar_one_or_none()
        
        if not analysis:
            print("❌ ERROR: Analysis not found")
            return False
        
        print(f"\n✓ Analysis found: {analysis.id}")
        print(f"  Status: {analysis.status.value}")
        
        # Verification checks
        checks_passed = 0
        total_checks = 4
        
        # Check 1: analysis.status = COMPLETE
        if analysis.status == AnalysisStatus.COMPLETE:
            print("✓ Check 1: analysis.status = COMPLETE")
            checks_passed += 1
        else:
            print(f"❌ Check 1 FAILED: analysis.status = {analysis.status.value} (expected COMPLETE)")
        
        # Check 2: review_record exists and links to shipment_id
        if analysis.review_record_id:
            result = await db.execute(select(ReviewRecord).where(ReviewRecord.id == analysis.review_record_id))
            review_record = result.scalar_one_or_none()
            
            if review_record:
                snapshot = review_record.object_snapshot
                shipment_id_in_snapshot = snapshot.get("shipment_id")
                
                if shipment_id_in_snapshot == str(shipment.id):
                    print(f"✓ Check 2: review_record exists and links to shipment_id")
                    checks_passed += 1
                else:
                    print(f"❌ Check 2 FAILED: review_record exists but shipment_id mismatch")
            else:
                print("❌ Check 2 FAILED: review_record not found")
        else:
            print("❌ Check 2 FAILED: analysis.review_record_id is None")
        
        # Check 3: regulatory_evaluations rows exist and link to review_id
        if analysis.review_record_id:
            result = await db.execute(
                select(RegulatoryEvaluation).where(RegulatoryEvaluation.review_id == analysis.review_record_id)
            )
            reg_evals = result.scalars().all()
            
            if reg_evals:
                print(f"✓ Check 3: regulatory_evaluations exist ({len(reg_evals)} rows) and link to review_id")
                checks_passed += 1
            else:
                print("❌ Check 3 FAILED: No regulatory_evaluations found")
        else:
            print("❌ Check 3 FAILED: Cannot check - review_record_id is None")
        
        # Check 4: result_json contains the 8-section data
        if analysis.result_json:
            result_json = analysis.result_json
            required_keys = ["shipment_id", "items", "evidence_map", "blockers", "review_status"]
            
            if all(key in result_json for key in required_keys):
                print(f"✓ Check 4: result_json contains required sections")
                checks_passed += 1
            else:
                missing = [k for k in required_keys if k not in result_json]
                print(f"❌ Check 4 FAILED: result_json missing keys: {missing}")
        else:
            print("❌ Check 4 FAILED: analysis.result_json is None")
        
        # Final result
        print(f"\n=== Happy Path Result: {checks_passed}/{total_checks} checks passed ===")
        return checks_passed == total_checks
        
    except Exception as e:
        print(f"\n❌ ERROR in happy path verification: {e}")
        import traceback
        traceback.print_exc()
        return False


async def verify_refusal_path(db: AsyncSession) -> bool:
    """
    Verify refusal path: Insufficient docs -> REFUSED analysis.
    
    Expected:
    - analysis.status = REFUSED
    - refusal_reason_code = INSUFFICIENT_DOCUMENTS
    - entitlement did not increment
    """
    print("\n=== VERIFICATION 2: Refusal Path ===")
    
    try:
        # Get test org and user
        result = await db.execute(select(Organization).limit(1))
        org = result.scalar_one_or_none()
        if not org:
            print("❌ ERROR: No organization found.")
            return False
        
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            print("❌ ERROR: No user found.")
            return False
        
        # Create shipment with only Packing List (insufficient)
        shipment = Shipment(
            organization_id=org.id,
            created_by=user.id,
            name=f"Test Refusal Path {datetime.utcnow().isoformat()}",
            status=ShipmentStatus.DRAFT
        )
        db.add(shipment)
        await db.flush()
        
        print(f"✓ Created shipment: {shipment.id}")
        
        # Create only Packing List (insufficient for eligibility)
        pl_doc = ShipmentDocument(
            shipment_id=shipment.id,
            organization_id=org.id,
            document_type=ShipmentDocumentType.PACKING_LIST,
            filename="test_pl.pdf",
            s3_key=f"test/{org.id}/{shipment.id}/pl.pdf",
            sha256_hash="test_pl_hash_789",
            retention_expires_at=datetime.utcnow(),
            uploaded_by=user.id
        )
        db.add(pl_doc)
        
        await db.commit()
        print(f"✓ Created document: Packing List only (insufficient)")
        
        # Get initial entitlement count
        entitlement_service = EntitlementService(db)
        entitlement = await entitlement_service.get_or_create(user.id)
        initial_count = entitlement.shipments_used
        print(f"✓ Initial entitlement count: {initial_count}/15")
        
        # Run analysis
        orchestration_service = AnalysisOrchestrationService(db)
        result = await orchestration_service.start_analysis(
            shipment_id=shipment.id,
            organization_id=org.id,
            actor_user_id=user.id
        )
        
        print(f"✓ Analysis started: {result.get('analysis_id')}")
        print(f"  Status: {result.get('status')}")
        
        # Check final state
        result = await db.execute(
            select(Analysis).where(Analysis.shipment_id == shipment.id).order_by(Analysis.created_at.desc())
        )
        analysis = result.scalar_one_or_none()
        
        if not analysis:
            print("❌ ERROR: Analysis not found")
            return False
        
        print(f"\n✓ Analysis found: {analysis.id}")
        print(f"  Status: {analysis.status.value}")
        
        # Verification checks
        checks_passed = 0
        total_checks = 3
        
        # Check 1: analysis.status = REFUSED
        if analysis.status == AnalysisStatus.REFUSED:
            print("✓ Check 1: analysis.status = REFUSED")
            checks_passed += 1
        else:
            print(f"❌ Check 1 FAILED: analysis.status = {analysis.status.value} (expected REFUSED)")
        
        # Check 2: refusal_reason_code = INSUFFICIENT_DOCUMENTS
        if analysis.refusal_reason_code == RefusalReasonCode.INSUFFICIENT_DOCUMENTS:
            print("✓ Check 2: refusal_reason_code = INSUFFICIENT_DOCUMENTS")
            checks_passed += 1
        else:
            print(f"❌ Check 2 FAILED: refusal_reason_code = {analysis.refusal_reason_code} (expected INSUFFICIENT_DOCUMENTS)")
        
        # Check 3: entitlement did not increment
        await db.refresh(entitlement)
        final_count = entitlement.shipments_used
        
        if final_count == initial_count:
            print(f"✓ Check 3: entitlement did not increment ({initial_count} -> {final_count})")
            checks_passed += 1
        else:
            print(f"❌ Check 3 FAILED: entitlement incremented ({initial_count} -> {final_count})")
        
        # Final result
        print(f"\n=== Refusal Path Result: {checks_passed}/{total_checks} checks passed ===")
        return checks_passed == total_checks
        
    except Exception as e:
        print(f"\n❌ ERROR in refusal path verification: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run both verification passes."""
    print("=" * 60)
    print("Analysis Integration Verification - Sprint 12")
    print("=" * 60)
    
    # Create database session
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        # Run verifications
        happy_path_passed = await verify_happy_path(db)
        refusal_path_passed = await verify_refusal_path(db)
        
        # Summary
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        print(f"Happy Path: {'✓ PASSED' if happy_path_passed else '❌ FAILED'}")
        print(f"Refusal Path: {'✓ PASSED' if refusal_path_passed else '❌ FAILED'}")
        
        if happy_path_passed and refusal_path_passed:
            print("\n✅ All verifications passed!")
            return 0
        else:
            print("\n❌ Some verifications failed. Please review errors above.")
            return 1


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
