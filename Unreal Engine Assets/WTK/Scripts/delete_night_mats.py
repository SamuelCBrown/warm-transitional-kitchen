import unreal
for p in ("/Game/WTK/HDRI/M_SkyDome_Night", "/Game/WTK/HDRI/M_GroundOutside_Night"):
    if unreal.EditorAssetLibrary.does_asset_exist(p):
        unreal.EditorAssetLibrary.delete_asset(p)
with open(r"C:\Users\Sam\Documents\Chess\tmp\WtkRelight2_20260927\delete_night_mats.txt", "w") as f:
    f.write("done")
