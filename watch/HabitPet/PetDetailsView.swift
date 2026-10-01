import SwiftUI

struct PetDetailsView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    private let generation: Int
    @State private var name: String
    @State private var species: String
    @State private var personality: String?
    init(pet: Pet) {
        generation=pet.generation
        _name=State(initialValue:pet.name)
        _species=State(initialValue:pet.species ?? "cat")
    }
    var body: some View {
        Form {
            PetAvatar(species:species,name:name).frame(height:110)
            TextField("Pet name",text:$name)
            Picker("Pet",selection:$species) {
                ForEach(PetCatalog.shared.pets) { pet in Text(pet.name).tag(pet.id) }
            }
            Picker("Personality",selection:Binding(get:{ personality ?? store.local.snapshot?.personality ?? "playful" },set:{personality=$0})) {
                ForEach(["gentle","playful","tsundere","energetic","calm"],id:\.self) { Text($0.capitalized).tag($0) }
            }
            if let pet=store.display?.pet { Text("Age: \(pet.currentAgeDays(at:.now)) days").font(.caption) }
            Button("Save pet") {
                Task { if await store.savePetDetails(generation:generation,name:name,species:species,personality:personality ?? store.local.snapshot?.personality ?? "playful") { dismiss() } }
            }.disabled(store.busy || store.syncing || !store.local.pending.isEmpty || name.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)
            if let message=store.statusMessage { Text(message).font(.caption2) }
            NavigationLink("Growth") {
                VStack(spacing:12) {
                if let pet=store.display?.pet { Text("\(pet.xpUntilNextLevel) XP to level \(pet.level+1)").font(.caption2) }
                Text("Food +5 XP. Fullness & Mood ≥70: +5 XP daily.").font(.caption2)
                }.padding().navigationTitle("Growth")
            }
        }.navigationTitle("My pet")
    }
}
