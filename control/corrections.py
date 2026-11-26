from __future__ import annotations

from typing import TYPE_CHECKING

from control.receipts import CorrectionReceipt
from editions.revisions import check_compatibility
from errors import conflict

if TYPE_CHECKING:
    from control.runtime import Runtime


def correct(runtime: Runtime, show_id: str, screen: str,
            revision: str, request: str) -> CorrectionReceipt:
    existing = runtime.receipts.get_correction(show_id, request, required=False)
    if existing is not None:
        if (existing.screen, existing.revision) != (screen, revision):
            raise conflict('correction request already has a different screen or revision')
        if existing.status == 'confirmed':
            return existing
    show = runtime.live_show(show_id, screen)
    if existing is None:
        initial = runtime.editions.get(show.initial_revision)
        target = runtime.editions.get(revision)
        check_compatibility(initial, target)
        existing = runtime.receipts.accept_correction(show_id, screen, request, revision)
    for pending in runtime.receipts.pending(show_id):
        if pending.epoch > existing.epoch:
            break
        runtime.screen.prepare_cutover(pending, runtime.editions.get(pending.revision))
        runtime.screen.apply_cutover(pending)
        runtime.receipts.record_dispatch(pending.show, pending.request)
    return runtime.receipts.get_correction(show_id, request)


def correction_status(runtime: Runtime, show_id: str, request: str) -> CorrectionReceipt:
    receipt = runtime.receipts.get_correction(show_id, request)
    if receipt.status == 'pending' and runtime.screen.find_cutover(show_id, receipt.screen, request) is not None:
        return runtime.receipts.record_dispatch(show_id, request)
    return receipt
