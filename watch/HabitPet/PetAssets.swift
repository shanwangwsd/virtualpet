import SwiftUI
import UIKit

/// All pet and item artwork is loaded from user-replaceable bundle resources.
private enum AssetImages {
    static let cache = NSCache<NSString, UIImage>()
    static var missing = Set<String>()
    static func load(_ key: String?) -> UIImage? {
        guard let key, !missing.contains(key) else { return nil }
        if let image=cache.object(forKey:key as NSString) { return image }
        guard let url=Bundle.main.url(forResource:key,withExtension:"png",subdirectory:"Assets"),
              let data=try? Data(contentsOf:url), !data.isEmpty, let image=UIImage(data:data) else { missing.insert(key); return nil }
        cache.countLimit=32
        cache.setObject(image,forKey:key as NSString)
        return image
    }
}
struct ResourceImage: View {
    let asset: String?
    var fallback: String? = nil
    var body: some View {
        if let image=AssetImages.load(asset) ?? AssetImages.load(fallback) {
            Image(uiImage:image).resizable().scaledToFit()
        } else {
            RoundedRectangle(cornerRadius:12).stroke(.secondary.opacity(0.4))
                .overlay(Text("Image not added").font(.caption2).foregroundStyle(.secondary))
        }
    }
}
struct PetAvatar: View {
    var species = "cat"
    var state = "normal"
    var name = "Mochi"
    var body: some View {
        ResourceImage(asset:PetCatalog.shared.asset(species:species,state:state),fallback:PetCatalog.shared.asset(species:species,state:"normal"))
            .accessibilityLabel("\(name), \(state)")
    }
}
struct InventoryView: View {
    @EnvironmentObject var store: AppStore
    let category: String
    var body: some View {
        List {
            if let pet=store.display?.pet {
                PetAvatar(species:pet.appearance.species,state:PetRules.imageState(pet,action:store.actionVisual),name:pet.name).frame(height:90)
                if let message=store.careMessage { Text(message).font(.caption2) }
            }
            let items=(store.display?.inventory.items ?? []).filter { $0.category==category && $0.quantity>0 }
            if items.isEmpty { Text("Complete a daily habit to earn an item.").font(.caption) }
            ForEach(items) { item in
                VStack {
                    ResourceImage(asset:item.asset).frame(height:70)
                    Text("\(item.name) ×\(item.quantity)")
                    Text("+\(item.effect) \(category=="food" ? "Fullness" : "Mood")").font(.caption2)
                    Button("Use") { Task { await store.action("use_item",payload:["item_id":item.id]) } }
                        .disabled(store.busy || store.display?.pet.state=="dead" || (category=="food" ? (store.display?.pet.hunger ?? 100)>=100 : (store.display?.pet.mood ?? 100)>=100))
                }
            }
            if let message=store.statusMessage { Text(message).font(.caption2) }
        }.navigationTitle(category=="food" ? "Food" : "Toys")
    }
}
struct RewardsView: View {
    @EnvironmentObject var store: AppStore
    var habitID:Int? = nil
    @State private var selectedCategory:String?
    private var rewards:[PendingReward] { RewardFlow.choices(store.display?.pendingRewards ?? [],habitID:habitID) }
    private var waiting:Bool { RewardFlow.waiting(store.local.pending,habitID:habitID) }
    var body: some View {
        List {
            if waiting {
                Text("Completion saved. Syncing your reward…").font(.caption)
                if store.syncing { ProgressView() }
            }
            ForEach(rewards) { reward in
                Section {
                    Button("Food") { choose(reward,category:0) }
                    Button("Toy") { choose(reward,category:1) }
                } header: { Text(reward.name) }
                .buttonStyle(.bordered)
                .disabled(store.busy || store.display?.pet.state=="dead")
            }
            if let selectedCategory {
                Text(store.local.pending.contains(where: { $0.kind=="claim_reward" }) ? "\(selectedCategory) selected. Syncing…" : "Reward added to \(selectedCategory).")
                    .font(.caption)
                NavigationLink("Open \(selectedCategory)") { InventoryView(category:selectedCategory=="Food" ? "food" : "toy") }
            } else if rewards.isEmpty && !waiting {
                Text("No unclaimed reward. Sync to check.").font(.caption)
            }
            if store.display?.pet.state=="dead" { Text("Start a new pet to claim saved rewards.").font(.caption2) }
            if let message=store.statusMessage { Text(message).font(.caption2) }
            Button("Sync") { Task { await store.refresh() } }.disabled(store.syncing || store.busy)
        }.navigationTitle("Choose reward")
    }
    private func choose(_ reward:PendingReward,category:Int) {
        Task {
            if await store.action("claim_reward",payload:["reward_id":reward.id,"category":category]) {
                selectedCategory=category==0 ? "Food" : "Toys"
            }
        }
    }
}


struct CareActionOverlay: View {
    @EnvironmentObject private var store:AppStore
    let pet:Pet
    let action:String
    @State private var moving=false
    private var title:String {
        switch action { case "eat": return "Yum!"; case "drink": return "Refreshing!"; case "rest": return "Rest time"; case "wake": return "Awake"; case "play": return "Playtime!"; default: return "Your pet" }
    }
    var body:some View {
        VStack(spacing:8) {
            PetAvatar(species:pet.appearance.species,state:PetRules.imageState(pet,action:action),name:pet.name)
                .frame(height:100)
                .scaleEffect(moving ? 1.06 : 0.96)
                .rotationEffect(.degrees(moving ? 4 : -4))
                .offset(y:moving ? -3 : 2)
            Text(title).font(.headline)
            if let message=store.careMessage { Text(message).font(.caption2).multilineTextAlignment(.center).lineLimit(3) }
            Button("Done") { store.dismissCareAnimation() }.font(.caption)
        }.padding(10).frame(maxWidth:.infinity,maxHeight:.infinity)
        .background(.black.opacity(0.96)).contentShape(Rectangle())
        .onAppear { withAnimation(.easeInOut(duration:0.45).repeatForever(autoreverses:true)) { moving=true } }
        .accessibilityLabel("\(pet.name): \(title)")
    }
}
