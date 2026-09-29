// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "HabitPetCore", platforms: [.macOS(.v13), .watchOS(.v10)], products: [.library(name: "HabitPetCore", targets: ["HabitPetCore"])], targets: [.target(name: "HabitPetCore", path: "HabitPet/Core"), .testTarget(name: "HabitPetCoreTests", dependencies: ["HabitPetCore"], path: "Tests")])
