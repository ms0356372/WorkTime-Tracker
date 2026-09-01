"""Platform-neutral sharing boundary."""
async def share_file(window,path):
    """Open Toga's native save dialog; native share adapters can extend this boundary."""
    await window.dialog(__import__("toga").InfoDialog("分享檔案",f"檔案位於：{path}"))
