"""Generate a dependency-free single-target watchOS Xcode project. Re-run after adding Swift files."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "watch"


def ident(text):
    return hashlib.sha256(text.encode()).hexdigest()[:24].upper()


def quote(text):
    return json.dumps(str(text))


objects = []


def add(key, body):
    objects.append(f"{ident(key)} = {{ {body} }};")


sources = sorted((ROOT / "HabitPet").rglob("*.swift"))
for p in sources:
    name = str(p.relative_to(ROOT))
    add(
        name,
        f'isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {quote(name)}; sourceTree = "<group>";',
    )
    add("build:" + name, f"isa = PBXBuildFile; fileRef = {ident(name)};")
add(
    "product",
    "isa = PBXFileReference; explicitFileType = wrapper.application; path = HabitPet.app; sourceTree = BUILT_PRODUCTS_DIR;",
)
add(
    "products",
    f'isa = PBXGroup; children = ({ident("product")},); name = Products; sourceTree = "<group>";',
)
add(
    "group",
    "isa = PBXGroup; children = ("
    + ",".join(ident(str(p.relative_to(ROOT))) for p in sources)
    + ","
    + ident("products")
    + ',); sourceTree = "<group>";',
)
add(
    "sources",
    "isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ("
    + ",".join(ident("build:" + str(p.relative_to(ROOT))) for p in sources)
    + ",); runOnlyForDeploymentPostprocessing = 0;",
)
add(
    "frameworks",
    "isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;",
)
add(
    "resources",
    "isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;",
)
for config in ("Debug", "Release"):
    base = "CLANG_ENABLE_MODULES = YES; SWIFT_VERSION = 5.0; WATCHOS_DEPLOYMENT_TARGET = 10.0; SDKROOT = watchos;"
    add(
        "project:" + config,
        f"isa = XCBuildConfiguration; buildSettings = {{ {base} }}; name = {config};",
    )
    opt = "-Onone" if config == "Debug" else "-O"
    settings = (
        base
        + f' PRODUCT_BUNDLE_IDENTIFIER = com.example.habitpet; PRODUCT_NAME = "$(TARGET_NAME)"; TARGETED_DEVICE_FAMILY = 4; SUPPORTED_PLATFORMS = "watchos watchsimulator"; INFOPLIST_FILE = HabitPet/Info.plist; GENERATE_INFOPLIST_FILE = NO; CODE_SIGN_ENTITLEMENTS = HabitPet/HabitPet.entitlements; CODE_SIGN_STYLE = Automatic; SWIFT_OPTIMIZATION_LEVEL = "{opt}"; SKIP_INSTALL = NO; LD_RUNPATH_SEARCH_PATHS = "$(inherited) @executable_path/Frameworks";'
    )
    add(
        "target:" + config,
        f"isa = XCBuildConfiguration; buildSettings = {{ {settings} }}; name = {config};",
    )
for owner in ("project", "target"):
    add(
        owner + ":configs",
        f"isa = XCConfigurationList; buildConfigurations = ({ident(owner + ':Debug')},{ident(owner + ':Release')},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;",
    )
add(
    "target",
    f'isa = PBXNativeTarget; buildConfigurationList = {ident("target:configs")}; buildPhases = ({ident("sources")},{ident("frameworks")},{ident("resources")},); buildRules = (); dependencies = (); name = HabitPet; productName = HabitPet; productReference = {ident("product")}; productType = "com.apple.product-type.application";',
)
add(
    "project",
    f'isa = PBXProject; attributes = {{ LastUpgradeCheck = 1600; }}; buildConfigurationList = {ident("project:configs")}; compatibilityVersion = "Xcode 14.0"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en,Base,); mainGroup = {ident("group")}; productRefGroup = {ident("products")}; projectDirPath = ""; projectRoot = ""; targets = ({ident("target")},);',
)
out = ROOT / "HabitPet.xcodeproj"
out.mkdir(exist_ok=True)
(out / "project.pbxproj").write_text(
    "// !$*UTF8*$!\n{ archiveVersion = 1; classes = {}; objectVersion = 56; objects = {\n"
    + "\n".join(objects)
    + "\n}; rootObject = "
    + ident("project")
    + "; }\n"
)
scheme = out / "xcshareddata" / "xcschemes"
scheme.mkdir(parents=True, exist_ok=True)
(scheme / "HabitPet.xcscheme").write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1600" version="1.3"><BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{ident("target")}" BuildableName="HabitPet.app" BlueprintName="HabitPet" ReferencedContainer="container:HabitPet.xcodeproj"/></BuildActionEntry></BuildActionEntries></BuildAction><LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{ident("target")}" BuildableName="HabitPet.app" BlueprintName="HabitPet" ReferencedContainer="container:HabitPet.xcodeproj"/></BuildableProductRunnable></LaunchAction><ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/></Scheme>''')
print(out)
