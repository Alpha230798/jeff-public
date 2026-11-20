import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

@main
struct JeffApp: App {
    @StateObject private var model = JeffModel()

    var body: some Scene {
        WindowGroup {
            JeffWindow()
                .environmentObject(model)
                .frame(minWidth: 900, minHeight: 620)
                .task {
                    await model.startService()
                }
                .onDisappear {
                    model.stopService()
                }
        }
        .windowStyle(.titleBar)
    }
}

private enum JeffPage: String, CaseIterable, Identifiable {
    case chat = "Chat"
    case documents = "Documents"
    case glossary = "Kreol Glossary"
    case browser = "Browser"
    case vpn = "VPN"
    case settings = "Settings"

    var id: String { rawValue }

    var symbol: String {
        switch self {
        case .chat: "bubble.left.and.bubble.right"
        case .documents: "doc.text"
        case .glossary: "character.book.closed"
        case .browser: "globe"
        case .vpn: "lock.shield"
        case .settings: "gearshape"
        }
    }
}

private struct JeffSettings: Codable {
    var ollamaURL = "http://localhost:11434"
    var chatModel = "qwen2.5:3b"
    var embeddingModel = "bge-m3"
    var mood = "😌 Calm"
    var replyLanguage = "Auto (match my message)"

    var requestValues: [String: String] {
        [
            "ollama_url": ollamaURL,
            "chat_model": chatModel,
            "embedding_model": embeddingModel,
            "mood": mood,
            "reply_language": replyLanguage,
        ]
    }
}

private struct ServiceHealth: Decodable {
    let ok: Bool
}

private struct RunningStatus: Decodable {
    let running: Bool
}

private struct OperationStatus: Decodable {
    let cleared: Bool?
    let deleted: Bool?
}

private struct ModelStatus: Decodable {
    let reachable: Bool
    let models: [String]
    let chatModelPresent: Bool
    let embeddingModelPresent: Bool

    enum CodingKeys: String, CodingKey {
        case reachable
        case models
        case chatModelPresent = "chat_model_present"
        case embeddingModelPresent = "embedding_model_present"
    }
}

private struct DocumentStatus: Decodable {
    let passages: Int
    let sources: [String]
    let errors: [String]?
}

private struct GlossaryEntry: Codable, Identifiable {
    let id: Int
    var kreolPhrase: String
    var alternativeSpellings: String
    var englishMeaning: String
    var frenchMeaning: String
    var example: String
    var pronunciationNotes: String
    var createdAt: String
    var updatedAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case kreolPhrase = "kreol_phrase"
        case alternativeSpellings = "alternative_spellings"
        case englishMeaning = "english_meaning"
        case frenchMeaning = "french_meaning"
        case example
        case pronunciationNotes = "pronunciation_notes"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    var draft: GlossaryDraft {
        GlossaryDraft(
            kreolPhrase: kreolPhrase,
            alternativeSpellings: alternativeSpellings,
            englishMeaning: englishMeaning,
            frenchMeaning: frenchMeaning,
            example: example,
            pronunciationNotes: pronunciationNotes
        )
    }
}

private struct GlossaryDraft: Decodable, Identifiable {
    var id = UUID()
    var kreolPhrase = ""
    var alternativeSpellings = ""
    var englishMeaning = ""
    var frenchMeaning = ""
    var example = ""
    var pronunciationNotes = ""

    init(
        kreolPhrase: String = "",
        alternativeSpellings: String = "",
        englishMeaning: String = "",
        frenchMeaning: String = "",
        example: String = "",
        pronunciationNotes: String = ""
    ) {
        self.kreolPhrase = kreolPhrase
        self.alternativeSpellings = alternativeSpellings
        self.englishMeaning = englishMeaning
        self.frenchMeaning = frenchMeaning
        self.example = example
        self.pronunciationNotes = pronunciationNotes
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        kreolPhrase = try container.decodeIfPresent(String.self, forKey: .kreolPhrase) ?? ""
        alternativeSpellings = try container.decodeIfPresent(String.self, forKey: .alternativeSpellings) ?? ""
        englishMeaning = try container.decodeIfPresent(String.self, forKey: .englishMeaning) ?? ""
        frenchMeaning = try container.decodeIfPresent(String.self, forKey: .frenchMeaning) ?? ""
        example = try container.decodeIfPresent(String.self, forKey: .example) ?? ""
        pronunciationNotes = try container.decodeIfPresent(String.self, forKey: .pronunciationNotes) ?? ""
    }

    enum CodingKeys: String, CodingKey {
        case kreolPhrase = "kreol_phrase"
        case alternativeSpellings = "alternative_spellings"
        case englishMeaning = "english_meaning"
        case frenchMeaning = "french_meaning"
        case example
        case pronunciationNotes = "pronunciation_notes"
    }

    var requestValues: [String: String] {
        [
            "kreol_phrase": kreolPhrase,
            "alternative_spellings": alternativeSpellings,
            "english_meaning": englishMeaning,
            "french_meaning": frenchMeaning,
            "example": example,
            "pronunciation_notes": pronunciationNotes,
        ]
    }
}

private struct SpellingSuggestion: Decodable, Identifiable {
    let variant: String
    let candidates: [String]

    var id: String { variant }
}

private struct BrowserPage: Decodable {
    let url: String
    let title: String
    let text: String
}

private struct VPNConnection: Decodable, Identifiable {
    let serviceID: String
    let label: String
    let status: String

    var id: String { serviceID }

    enum CodingKeys: String, CodingKey {
        case serviceID = "service_id"
        case label
        case status
    }
}

private struct Passage: Decodable, Identifiable {
    let citation: String
    let source: String
    let text: String

    var id: String { citation }
}

private struct ChatReply: Decodable {
    let answer: String
    let passages: [Passage]
    let glossaryEntries: [GlossaryEntry]
    let spellingSuggestions: [SpellingSuggestion]

    enum CodingKeys: String, CodingKey {
        case answer
        case passages
        case glossaryEntries = "glossary_entries"
        case spellingSuggestions = "spelling_suggestions"
    }
}

private struct ChatTurn: Identifiable {
    let id = UUID()
    let role: String
    let content: String
    var passages: [Passage] = []
    var glossaryEntries: [GlossaryEntry] = []
    var spellingSuggestions: [SpellingSuggestion] = []
}

private struct VPNIntentResponse: Decodable {
    let handled: Bool
    let reply: String?
    let confirmation: VPNIntentConfirmation?
}

private struct VPNIntentConfirmation: Decodable {
    let action: String
    let serviceID: String
    let label: String
    let status: String

    enum CodingKeys: String, CodingKey {
        case action
        case serviceID = "service_id"
        case label
        case status
    }
}

private struct VPNConfirmation {
    let action: String
    let connection: VPNConnection

    var title: String {
        action == "connect"
            ? "Connect to \(connection.label)?"
            : "Disconnect from \(connection.label)?"
    }

    var buttonTitle: String {
        action == "connect" ? "Connect" : "Disconnect"
    }
}

private struct ServiceErrorPayload: Decodable {
    let error: String
}

private struct ServiceClient {
    let baseURL: URL
    let token: String

    func request<Response: Decodable>(
        _ path: String,
        method: String = "GET",
        body: [String: Any]? = nil
    ) async throws -> Response {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = method
        request.timeoutInterval = 240
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw JeffError.message("Jeff's local service returned an invalid response.")
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            let detail = (try? JSONDecoder().decode(ServiceErrorPayload.self, from: data).error)
                ?? "Jeff's local service returned HTTP \(httpResponse.statusCode)."
            throw JeffError.message(detail)
        }
        do {
            return try JSONDecoder().decode(Response.self, from: data)
        } catch {
            throw JeffError.message("Jeff's local service returned an invalid response.")
        }
    }
}

private enum JeffError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let text): text
        }
    }
}

@MainActor
private final class JeffModel: ObservableObject {
    @Published var settings: JeffSettings {
        didSet { saveSettings() }
    }
    @Published var serviceState = "Starting Jeff…"
    @Published var internetReachable: Bool?
    @Published var downloadSpeedMbps: Double?
    @Published var alertText = ""
    @Published var isWorking = false
    @Published var modelStatus: ModelStatus?
    @Published var chatTurns: [ChatTurn] = []
    @Published var documentStatus = DocumentStatus(passages: 0, sources: [], errors: nil)
    @Published var glossaryEntries: [GlossaryEntry] = []
    @Published var glossaryCandidates: [GlossaryDraft] = []
    @Published var spellingMemories: [String: String] = [:]
    @Published var browserRunning = false
    @Published var browserPage: BrowserPage?
    @Published var browserContextAdded = false
    @Published var vpnConnections: [VPNConnection] = []
    @Published var pendingVPNConfirmation: VPNConfirmation?

    private var serviceProcess: Process?
    private var serviceClient: ServiceClient?
    private var launchLogHandle: FileHandle?
    private var lastSpeedTestAt: Date?

    init() {
        if let data = UserDefaults.standard.data(forKey: "jeff.settings"),
           let saved = try? JSONDecoder().decode(JeffSettings.self, from: data) {
            settings = saved
        } else {
            settings = JeffSettings()
        }
    }

    func startService() async {
        if let process = serviceProcess, process.isRunning {
            return
        }
        serviceState = "Starting Jeff…"
        do {
            let port = try reservePort()
            let token = UUID().uuidString + UUID().uuidString
            let helper = Bundle.main.bundleURL
                .appending(path: "Contents/Resources/JeffService/JeffService")
            guard FileManager.default.isExecutableFile(atPath: helper.path) else {
                throw JeffError.message("Jeff's local service is missing from this app package.")
            }

            let logURL = FileManager.default.homeDirectoryForCurrentUser
                .appending(path: "Library/Logs/Jeff/native-service-launch.log")
            try FileManager.default.createDirectory(
                at: logURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            if !FileManager.default.fileExists(atPath: logURL.path) {
                FileManager.default.createFile(atPath: logURL.path, contents: nil)
            }
            let logHandle = try FileHandle(forWritingTo: logURL)
            try logHandle.seekToEnd()

            let process = Process()
            process.executableURL = helper
            process.arguments = ["--host", "127.0.0.1", "--port", String(port)]
            var environment = ProcessInfo.processInfo.environment
            environment["JEFF_SERVICE_TOKEN"] = token
            process.environment = environment
            process.standardOutput = logHandle
            process.standardError = logHandle
            try process.run()

            serviceProcess = process
            launchLogHandle = logHandle
            guard let baseURL = URL(string: "http://127.0.0.1:\(port)") else {
                throw JeffError.message("Jeff could not create its local service address.")
            }
            let client = ServiceClient(
                baseURL: baseURL,
                token: token
            )
            serviceClient = client
            for _ in 0..<60 {
                if !process.isRunning {
                    throw JeffError.message(
                        "Jeff's local service stopped while starting. Check ~/Library/Logs/Jeff/."
                    )
                }
                do {
                    let _: ServiceHealth = try await client.request("/api/health")
                    serviceState = "Jeff is ready"
                    await refreshDocuments()
                    await refreshGlossary()
                    return
                } catch {
                    try await Task.sleep(for: .milliseconds(150))
                }
            }
            throw JeffError.message(
                "Jeff's local service did not start. Check ~/Library/Logs/Jeff/."
            )
        } catch {
            serviceState = "Jeff could not start"
            present(error)
        }
    }

    func stopService() {
        if let process = serviceProcess, process.isRunning {
            process.terminate()
        }
        serviceProcess = nil
        serviceClient = nil
        try? launchLogHandle?.close()
        launchLogHandle = nil
        serviceState = "Jeff is closed"
    }

    func refreshInternetStatus() async {
        var connectivityRequest = URLRequest(
            url: URL(string: "https://www.apple.com/library/test/success.html")!
        )
        connectivityRequest.timeoutInterval = 10
        do {
            let (_, response) = try await URLSession.shared.data(for: connectivityRequest)
            guard let httpResponse = response as? HTTPURLResponse,
                  (200..<300).contains(httpResponse.statusCode) else {
                throw URLError(.badServerResponse)
            }
            internetReachable = true
        } catch {
            internetReachable = false
            downloadSpeedMbps = nil
            return
        }

        guard lastSpeedTestAt.map({ Date().timeIntervalSince($0) >= 300 }) ?? true else {
            return
        }
        lastSpeedTestAt = Date()

        var speedRequest = URLRequest(
            url: URL(string: "https://speed.cloudflare.com/__down?bytes=1000000")!
        )
        speedRequest.cachePolicy = .reloadIgnoringLocalCacheData
        speedRequest.timeoutInterval = 20
        let startedAt = Date()
        do {
            let (data, response) = try await URLSession.shared.data(for: speedRequest)
            guard let httpResponse = response as? HTTPURLResponse,
                  (200..<300).contains(httpResponse.statusCode),
                  !data.isEmpty else {
                throw URLError(.badServerResponse)
            }
            let duration = Date().timeIntervalSince(startedAt)
            if duration > 0 {
                downloadSpeedMbps = Double(data.count) * 8 / duration / 1_000_000
            } else {
                downloadSpeedMbps = nil
            }
        } catch {
            downloadSpeedMbps = nil
        }
    }

    func checkModels() async {
        do {
            let result: ModelStatus = try await request(
                "/api/models",
                method: "POST",
                body: ["settings": settings.requestValues]
            )
            modelStatus = result
        } catch {
            modelStatus = nil
            present(error)
        }
    }

    func sendChat(_ question: String) async {
        let trimmed = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isWorking else { return }
        chatTurns.append(ChatTurn(role: "user", content: trimmed))
        let history = chatTurns.dropLast().suffix(8).map {
            ["role": $0.role, "content": $0.content]
        }
        var body: [String: Any] = [
            "question": trimmed,
            "history": history,
            "settings": settings.requestValues,
        ]
        if browserContextAdded, let page = browserPage {
            body["browser_context"] = [
                "title": page.title,
                "url": page.url,
                "text": page.text,
            ]
        }
        isWorking = true
        defer { isWorking = false }
        do {
            let vpnIntent: VPNIntentResponse = try await request(
                "/api/vpn/request",
                method: "POST",
                body: ["question": trimmed]
            )
            if vpnIntent.handled {
                if let reply = vpnIntent.reply {
                    chatTurns.append(ChatTurn(role: "assistant", content: reply))
                }
                if let confirmation = vpnIntent.confirmation {
                    let connection = VPNConnection(
                        serviceID: confirmation.serviceID,
                        label: confirmation.label,
                        status: confirmation.status
                    )
                    pendingVPNConfirmation = VPNConfirmation(
                        action: confirmation.action,
                        connection: connection
                    )
                }
                chatTurns = Array(chatTurns.suffix(20))
                return
            }
            let reply: ChatReply = try await request("/api/chat", method: "POST", body: body)
            chatTurns.append(
                ChatTurn(
                    role: "assistant",
                    content: reply.answer,
                    passages: reply.passages,
                    glossaryEntries: reply.glossaryEntries,
                    spellingSuggestions: reply.spellingSuggestions
                )
            )
            chatTurns = Array(chatTurns.suffix(20))
            if browserContextAdded {
                browserContextAdded = false
            }
        } catch {
            present(error)
        }
    }

    func indexDocuments(urls: [URL]) async {
        guard !isWorking else { return }
        isWorking = true
        defer { isWorking = false }
        do {
            var files: [[String: String]] = []
            for url in urls {
                let hasScope = url.startAccessingSecurityScopedResource()
                defer {
                    if hasScope { url.stopAccessingSecurityScopedResource() }
                }
                let data = try Data(contentsOf: url)
                guard data.count <= 24 * 1024 * 1024 else {
                    throw JeffError.message("\(url.lastPathComponent) is larger than 24 MB.")
                }
                files.append([
                    "name": url.lastPathComponent,
                    "data": data.base64EncodedString(),
                ])
            }
            let result: DocumentStatus = try await request(
                "/api/documents",
                method: "POST",
                body: ["settings": settings.requestValues, "files": files]
            )
            documentStatus = result
            if let errors = result.errors, !errors.isEmpty {
                alertText = "Some documents could not be read:\n" + errors.joined(separator: "\n")
            }
        } catch {
            present(error)
        }
    }

    func clearDocuments() async {
        do {
            let _: OperationStatus = try await request(
                "/api/documents/clear",
                method: "POST",
                body: [:]
            )
            documentStatus = DocumentStatus(passages: 0, sources: [], errors: nil)
        } catch {
            present(error)
        }
    }

    func refreshDocuments() async {
        do {
            documentStatus = try await request("/api/documents")
        } catch {
            present(error)
        }
    }

    func refreshGlossary() async {
        do {
            glossaryEntries = try await request("/api/glossary")
        } catch {
            present(error)
        }
    }

    func refreshSpellings() async {
        do {
            spellingMemories = try await request("/api/spellings")
        } catch {
            present(error)
        }
    }

    func rememberSpelling(_ suggestion: SpellingSuggestion, as canonical: String) async {
        do {
            let _: OperationStatus = try await request(
                "/api/spellings/remember",
                method: "POST",
                body: ["variant": suggestion.variant, "canonical": canonical]
            )
            spellingMemories[suggestion.variant] = canonical
            removeSpellingSuggestion(suggestion.variant)
        } catch {
            present(error)
        }
    }

    func forgetSpelling(_ variant: String) async {
        do {
            struct ForgetResult: Decodable { let forgotten: Bool }
            let result: ForgetResult = try await request(
                "/api/spellings/forget",
                method: "POST",
                body: ["variant": variant]
            )
            if result.forgotten {
                spellingMemories.removeValue(forKey: variant)
            }
        } catch {
            present(error)
        }
    }

    func skipSpelling(_ variant: String) {
        removeSpellingSuggestion(variant)
    }

    func saveGlossary(_ draft: GlossaryDraft, id: Int?) async {
        do {
            let path = id.map { "/api/glossary/\($0)" } ?? "/api/glossary"
            let method = id == nil ? "POST" : "PUT"
            let _: GlossaryEntry = try await request(
                path,
                method: method,
                body: draft.requestValues
            )
            await refreshGlossary()
        } catch {
            present(error)
        }
    }

    func deleteGlossaryEntry(_ id: Int) async {
        do {
            let _: OperationStatus = try await request(
                "/api/glossary/\(id)",
                method: "DELETE"
            )
            await refreshGlossary()
        } catch {
            present(error)
        }
    }

    func importGlossaryPDF(_ url: URL) async {
        do {
            let hasScope = url.startAccessingSecurityScopedResource()
            defer {
                if hasScope { url.stopAccessingSecurityScopedResource() }
            }
            let data = try Data(contentsOf: url)
            guard data.count <= 24 * 1024 * 1024 else {
                throw JeffError.message("The PDF is larger than 24 MB.")
            }
            struct ImportResult: Decodable {
                let candidates: [GlossaryDraft]
                let truncated: Bool
            }
            let result: ImportResult = try await request(
                "/api/glossary/import",
                method: "POST",
                body: [
                    "settings": settings.requestValues,
                    "name": url.lastPathComponent,
                    "data": data.base64EncodedString(),
                ]
            )
            glossaryCandidates = result.candidates
            if result.truncated {
                alertText = "Jeff read only the first part of that PDF."
            }
            if result.candidates.isEmpty {
                alertText = "Jeff did not find any reviewable glossary entries in that PDF."
            }
        } catch {
            present(error)
        }
    }

    func saveGlossaryCandidates() async {
        do {
            struct SaveResult: Decodable {
                let added: Int
                let skipped: [String]
            }
            let result: SaveResult = try await request(
                "/api/glossary/bulk",
                method: "POST",
                body: ["entries": glossaryCandidates.map(\.requestValues)]
            )
            glossaryCandidates = []
            await refreshGlossary()
            if !result.skipped.isEmpty {
                alertText = "Added \(result.added) entries. Already-existing phrases were skipped: "
                    + result.skipped.joined(separator: ", ")
            }
        } catch {
            present(error)
        }
    }

    func startBrowser() async {
        do {
            let _: RunningStatus = try await request("/api/browser/start", method: "POST", body: [:])
            browserRunning = true
        } catch {
            present(error)
        }
    }

    func navigateBrowser(to address: String) async {
        do {
            struct NavigateResult: Decodable { let url: String }
            let _: NavigateResult = try await request(
                "/api/browser/navigate",
                method: "POST",
                body: ["address": address]
            )
            await readBrowserPage()
        } catch {
            present(error)
        }
    }

    func readBrowserPage() async {
        do {
            browserPage = try await request("/api/browser/page")
        } catch {
            present(error)
        }
    }

    func stopBrowser() async {
        do {
            let _: RunningStatus = try await request("/api/browser/stop", method: "POST", body: [:])
            browserRunning = false
            browserPage = nil
            browserContextAdded = false
        } catch {
            present(error)
        }
    }

    func refreshVPN() async {
        do {
            vpnConnections = try await request("/api/vpn")
        } catch {
            present(error)
        }
    }

    func askToChangeVPN(_ action: String, connection: VPNConnection) {
        pendingVPNConfirmation = VPNConfirmation(action: action, connection: connection)
    }

    func performVPNChange() async {
        guard let confirmation = pendingVPNConfirmation else { return }
        defer { pendingVPNConfirmation = nil }
        do {
            struct VPNResult: Decodable { let status: String }
            let result: VPNResult = try await request(
                "/api/vpn/\(confirmation.connection.serviceID)/\(confirmation.action)",
                method: "POST",
                body: [:]
            )
            let current = confirmation.connection.label
            let outcome: String
            if confirmation.action == "connect" && result.status.caseInsensitiveCompare("Connected") == .orderedSame {
                outcome = "Connected to \(current). Check the VPN status before relying on it."
            } else if confirmation.action == "disconnect" && result.status.caseInsensitiveCompare("Disconnected") == .orderedSame {
                outcome = "Disconnected from \(current)."
            } else {
                outcome = "\(current) is \(result.status.lowercased()). Check the VPN status before relying on it."
            }
            chatTurns.append(ChatTurn(role: "assistant", content: outcome))
            chatTurns = Array(chatTurns.suffix(20))
            await refreshVPN()
        } catch {
            present(error)
        }
    }

    private func request<Response: Decodable>(
        _ path: String,
        method: String = "GET",
        body: [String: Any]? = nil
    ) async throws -> Response {
        guard let serviceClient else {
            throw JeffError.message("Jeff's local service is not running. Restart the app and try again.")
        }
        return try await serviceClient.request(path, method: method, body: body)
    }

    private func saveSettings() {
        guard let data = try? JSONEncoder().encode(settings) else { return }
        UserDefaults.standard.set(data, forKey: "jeff.settings")
    }

    private func present(_ error: Error) {
        alertText = error.localizedDescription
    }

    private func removeSpellingSuggestion(_ variant: String) {
        guard let index = chatTurns.lastIndex(where: { $0.role == "assistant" }) else { return }
        chatTurns[index].spellingSuggestions.removeAll { $0.variant == variant }
    }

    private func reservePort() throws -> UInt16 {
        let descriptor = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard descriptor >= 0 else {
            throw JeffError.message("Jeff could not reserve a local service port.")
        }
        defer { Darwin.close(descriptor) }

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = 0
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let bindResult = withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(descriptor, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard bindResult == 0 else {
            throw JeffError.message("Jeff could not reserve a local service port.")
        }
        var selected = sockaddr_in()
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        let result = withUnsafeMutablePointer(to: &selected) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.getsockname(descriptor, $0, &length)
            }
        }
        guard result == 0, selected.sin_port != 0 else {
            throw JeffError.message("Jeff could not reserve a local service port.")
        }
        return UInt16(bigEndian: selected.sin_port)
    }
}

private struct JeffWindow: View {
    @EnvironmentObject private var model: JeffModel
    @State private var selection: JeffPage? = .chat

    private var serviceIndicatorColor: Color {
        switch model.serviceState {
        case "Jeff is ready": .green
        case "Starting Jeff…": .orange
        default: .red
        }
    }

    private var internetIndicatorColor: Color {
        switch model.internetReachable {
        case true: .green
        case false: .red
        case nil: .orange
        }
    }

    private var internetStatusText: String {
        guard let reachable = model.internetReachable else {
            return "Internet · Checking…"
        }
        guard reachable else {
            return "Internet · Offline"
        }
        guard let speed = model.downloadSpeedMbps else {
            return "Internet · Online · Speed unavailable"
        }
        return String(format: "Internet · Online · %.1f Mbps", speed)
    }

    private var sidebarFooter: some View {
        VStack(alignment: .leading, spacing: 8) {
            statusRow(model.serviceState, color: serviceIndicatorColor)
            statusRow(internetStatusText, color: internetIndicatorColor)
                .help("Connectivity is checked every 30 seconds. Download speed is estimated every 5 minutes.")
        }
        .font(.caption)
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 8))
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    var body: some View {
        NavigationSplitView {
            List(JeffPage.allCases, selection: $selection) { page in
                Label(page.rawValue, systemImage: page.symbol)
                    .tag(page)
            }
            .listStyle(.sidebar)
            .navigationTitle("Jeff")
            .safeAreaInset(edge: .bottom) {
                sidebarFooter
            }
        } detail: {
            Group {
                switch selection ?? .chat {
                case .chat:
                    ChatView()
                case .documents:
                    DocumentsView()
                case .glossary:
                    GlossaryView()
                case .browser:
                    BrowserView()
                case .vpn:
                    VPNView()
                case .settings:
                    SettingsView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .alert("Jeff", isPresented: Binding(
            get: { !model.alertText.isEmpty },
            set: { if !$0 { model.alertText = "" } }
        )) {
            Button("OK") { model.alertText = "" }
        } message: {
            Text(model.alertText)
        }
        .task {
            while !Task.isCancelled {
                await model.refreshInternetStatus()
                do {
                    try await Task.sleep(for: .seconds(30))
                } catch {
                    return
                }
            }
        }
        .confirmationDialog(
            model.pendingVPNConfirmation?.title ?? "Change VPN connection?",
            isPresented: Binding(
                get: { model.pendingVPNConfirmation != nil },
                set: { if !$0 { model.pendingVPNConfirmation = nil } }
            ),
            titleVisibility: .visible
        ) {
            if let confirmation = model.pendingVPNConfirmation {
                Button(
                    confirmation.buttonTitle,
                    role: confirmation.action == "disconnect" ? .destructive : nil
                ) {
                    Task { await model.performVPNChange() }
                }
                Button("Cancel", role: .cancel) {
                    model.pendingVPNConfirmation = nil
                }
            }
        } message: {
            Text("This changes the Mac's VPN connection for all apps, not only Jeff.")
        }
    }

    private func statusRow(_ title: String, color: Color) -> some View {
        HStack(spacing: 8) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
                .accessibilityHidden(true)
            Text(title)
                .lineLimit(1)
        }
    }
}

private struct ChatView: View {
    @EnvironmentObject private var model: JeffModel
    @State private var message = ""

    var body: some View {
        VStack(spacing: 0) {
            if model.browserContextAdded, let page = model.browserPage {
                HStack {
                    Label("Next message includes \(page.title.isEmpty ? page.url : page.title)", systemImage: "globe")
                    Spacer()
                    Button("Remove") { model.browserContextAdded = false }
                        .buttonStyle(.borderless)
                }
                .font(.caption)
                .padding()
            }
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 16) {
                        if model.chatTurns.isEmpty {
                            VStack(spacing: 10) {
                                Image(systemName: "bubble.left.and.bubble.right")
                                    .font(.largeTitle)
                                    .foregroundStyle(.secondary)
                                Text("Hello, how can I help?")
                                    .font(.title2.weight(.semibold))
                                Text("Your private assistant for questions, documents, and ideas.")
                                    .foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity, minHeight: 360)
                        }
                        ForEach(model.chatTurns) { turn in
                            ChatBubble(turn: turn)
                                .id(turn.id)
                        }
                        if model.isWorking {
                            HStack {
                                ProgressView()
                                Text("Jeff is thinking…")
                                    .foregroundStyle(.secondary)
                            }
                            .padding(.horizontal)
                        }
                    }
                    .padding()
                }
                .onChange(of: model.chatTurns.count) { _ in
                    if let last = model.chatTurns.last {
                        withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                    }
                }
            }
            Divider()
            HStack(alignment: .bottom) {
                TextField("Message Jeff…", text: $message, axis: .vertical)
                    .lineLimit(1...5)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit(send)
                    .disabled(model.isWorking)
                Button(action: send) {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.title2)
                }
                .buttonStyle(.plain)
                .disabled(message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || model.isWorking)
                .help("Send message")
            }
            .padding()
        }
        .navigationTitle("Chat")
    }

    private func send() {
        let outgoing = message
        message = ""
        Task { await model.sendChat(outgoing) }
    }
}

private struct ChatBubble: View {
    @EnvironmentObject private var model: JeffModel
    let turn: ChatTurn

    var body: some View {
        HStack {
            if turn.role == "assistant" { Spacer(minLength: 80) }
            VStack(alignment: .leading, spacing: 10) {
                Text(turn.content)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if !turn.passages.isEmpty {
                    DisclosureGroup("Sources Jeff used") {
                        ForEach(turn.passages) { passage in
                            VStack(alignment: .leading, spacing: 4) {
                                Text("[\(passage.citation)] \(passage.source)")
                                    .font(.caption.weight(.semibold))
                                Text(passage.text)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            .padding(.vertical, 4)
                        }
                    }
                    .font(.caption)
                }
                if !turn.glossaryEntries.isEmpty {
                    DisclosureGroup("Kreol glossary entries used") {
                        ForEach(turn.glossaryEntries) { entry in
                            VStack(alignment: .leading, spacing: 3) {
                                Text(entry.kreolPhrase).font(.caption.weight(.semibold))
                                if !entry.englishMeaning.isEmpty {
                                    Text("English: \(entry.englishMeaning)").font(.caption)
                                }
                                if !entry.frenchMeaning.isEmpty {
                                    Text("French: \(entry.frenchMeaning)").font(.caption)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                    .font(.caption)
                }
                ForEach(turn.spellingSuggestions) { suggestion in
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Did you mean one of these for “\(suggestion.variant)”?")
                            .font(.caption.weight(.semibold))
                        HStack {
                            ForEach(suggestion.candidates, id: \.self) { candidate in
                                Button("Remember \(candidate)") {
                                    Task { await model.rememberSpelling(suggestion, as: candidate) }
                                }
                                .buttonStyle(.bordered)
                                .controlSize(.small)
                            }
                            Button("Skip") {
                                model.skipSpelling(suggestion.variant)
                            }
                            .buttonStyle(.borderless)
                            .controlSize(.small)
                        }
                    }
                    .padding(8)
                    .background(Color.accentColor.opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
            }
            .padding(12)
            .background(turn.role == "assistant" ? Color(nsColor: .controlBackgroundColor) : Color.accentColor.opacity(0.13))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            if turn.role == "user" { Spacer(minLength: 80) }
        }
    }
}

private struct DocumentsView: View {
    @EnvironmentObject private var model: JeffModel
    @State private var showingImporter = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Documents").font(.largeTitle.bold())
            Text("Add files when you want Jeff to answer questions using their contents. Supported formats are PDF, DOCX, TXT, and Markdown.")
                .foregroundStyle(.secondary)
            GroupBox("Add documents") {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Document text and relevant excerpts are sent only to your configured local Ollama server when indexed or used in a question.")
                        .font(.callout)
                    Button("Choose documents to index…") { showingImporter = true }
                        .buttonStyle(.borderedProminent)
                        .disabled(model.isWorking)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 4)
            }
            GroupBox("Indexed for this session") {
                VStack(alignment: .leading, spacing: 8) {
                    if model.documentStatus.passages == 0 {
                        Text("No documents are indexed yet.")
                            .foregroundStyle(.secondary)
                    } else {
                        Text("\(model.documentStatus.passages) passages")
                            .fontWeight(.semibold)
                        ForEach(model.documentStatus.sources, id: \.self) { source in
                            Label(source, systemImage: "doc.text")
                        }
                        Button("Clear document index", role: .destructive) {
                            Task { await model.clearDocuments() }
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 4)
            }
            Spacer()
        }
        .padding(24)
        .navigationTitle("Documents")
        .fileImporter(
            isPresented: $showingImporter,
            allowedContentTypes: [
                .pdf,
                .plainText,
                UTType(filenameExtension: "md") ?? .plainText,
                UTType(filenameExtension: "docx") ?? .data,
            ],
            allowsMultipleSelection: true
        ) { result in
            switch result {
            case .success(let urls):
                Task { await model.indexDocuments(urls: urls) }
            case .failure(let error):
                model.alertText = error.localizedDescription
            }
        }
    }
}

private struct GlossaryView: View {
    @EnvironmentObject private var model: JeffModel
    @State private var query = ""
    @State private var showEditor = false
    @State private var showPDFImporter = false
    @State private var editingID: Int?
    @State private var draft = GlossaryDraft()

    private var filteredEntries: [GlossaryEntry] {
        guard !query.isEmpty else { return model.glossaryEntries }
        return model.glossaryEntries.filter {
            "\($0.kreolPhrase) \($0.alternativeSpellings) \($0.englishMeaning) \($0.frenchMeaning)"
                .localizedCaseInsensitiveContains(query)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Kreol Glossary").font(.largeTitle.bold())
                Spacer()
                Button("Import PDF…", systemImage: "doc.badge.plus") { showPDFImporter = true }
                Button("Add entry", systemImage: "plus") {
                    editingID = nil
                    draft = GlossaryDraft()
                    showEditor = true
                }
                .buttonStyle(.borderedProminent)
            }
            TextField("Search words and meanings", text: $query)
                .textFieldStyle(.roundedBorder)
            List {
                ForEach(filteredEntries) { entry in
                    VStack(alignment: .leading, spacing: 5) {
                        HStack {
                            Text(entry.kreolPhrase).font(.headline)
                            Spacer()
                            Button("Edit") {
                                editingID = entry.id
                                draft = entry.draft
                                showEditor = true
                            }
                            .buttonStyle(.borderless)
                            Button(role: .destructive) {
                                Task { await model.deleteGlossaryEntry(entry.id) }
                            } label: {
                                Image(systemName: "trash")
                            }
                            .buttonStyle(.borderless)
                            .help("Delete \(entry.kreolPhrase)")
                        }
                        if !entry.alternativeSpellings.isEmpty {
                            Text("Also written: \(entry.alternativeSpellings)")
                        }
                        if !entry.englishMeaning.isEmpty {
                            Text("English: \(entry.englishMeaning)")
                        }
                        if !entry.frenchMeaning.isEmpty {
                            Text("French: \(entry.frenchMeaning)")
                        }
                        if !entry.example.isEmpty {
                            Text("Example: \(entry.example)")
                        }
                    }
                    .padding(.vertical, 4)
                }
                if !model.glossaryCandidates.isEmpty {
                    Section("Review imported candidates before saving") {
                        ForEach($model.glossaryCandidates) { $candidate in
                            DisclosureGroup(candidate.kreolPhrase.isEmpty ? "New candidate" : candidate.kreolPhrase) {
                                GlossaryFields(draft: $candidate)
                            }
                        }
                        HStack {
                            Button("Discard candidates", role: .destructive) {
                                model.glossaryCandidates = []
                            }
                            Spacer()
                            Button("Save reviewed entries") {
                                Task { await model.saveGlossaryCandidates() }
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }
                }
                if !model.spellingMemories.isEmpty {
                    Section("My spellings") {
                        ForEach(model.spellingMemories.keys.sorted(), id: \.self) { variant in
                            HStack {
                                Text("\(variant) → \(model.spellingMemories[variant] ?? "")")
                                Spacer()
                                Button("Forget", role: .destructive) {
                                    Task { await model.forgetSpelling(variant) }
                                }
                                .buttonStyle(.borderless)
                            }
                        }
                    }
                }
            }
            .listStyle(.inset)
        }
        .padding(24)
        .navigationTitle("Kreol Glossary")
        .task {
            await model.refreshGlossary()
            await model.refreshSpellings()
        }
        .sheet(isPresented: $showEditor) {
            GlossaryEditor(draft: $draft, onSave: {
                Task {
                    await model.saveGlossary(draft, id: editingID)
                    showEditor = false
                }
            })
            .frame(minWidth: 480, minHeight: 480)
        }
        .fileImporter(
            isPresented: $showPDFImporter,
            allowedContentTypes: [.pdf],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                if let url = urls.first {
                    Task { await model.importGlossaryPDF(url) }
                }
            case .failure(let error):
                model.alertText = error.localizedDescription
            }
        }
    }
}

private struct GlossaryFields: View {
    @Binding var draft: GlossaryDraft

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            TextField("Kreol phrase", text: $draft.kreolPhrase)
            TextField("Alternative spellings", text: $draft.alternativeSpellings)
            TextField("English meaning", text: $draft.englishMeaning)
            TextField("French meaning", text: $draft.frenchMeaning)
            TextField("Example", text: $draft.example)
            TextField("Pronunciation or spelling notes", text: $draft.pronunciationNotes)
        }
        .textFieldStyle(.roundedBorder)
        .padding(.vertical, 6)
    }
}

private struct GlossaryEditor: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var draft: GlossaryDraft
    let onSave: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(draft.kreolPhrase.isEmpty ? "Add glossary entry" : "Edit glossary entry")
                .font(.title2.bold())
            GlossaryFields(draft: $draft)
            Spacer()
            HStack {
                Button("Cancel", role: .cancel) { dismiss() }
                Spacer()
                Button("Save entry", action: onSave)
                    .buttonStyle(.borderedProminent)
                    .disabled(draft.kreolPhrase.trimmingCharacters(in: .whitespaces).isEmpty
                        || (draft.englishMeaning.trimmingCharacters(in: .whitespaces).isEmpty
                            && draft.frenchMeaning.trimmingCharacters(in: .whitespaces).isEmpty))
            }
        }
        .padding(24)
    }
}

private struct BrowserView: View {
    @EnvironmentObject private var model: JeffModel
    @State private var address = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Browser").font(.largeTitle.bold())
            Text("Jeff opens pages in a separate Firefox Developer Edition profile. Reading is local; page text is sent to Ollama only if you add it to a chat message.")
                .foregroundStyle(.secondary)
            GroupBox("Separate Firefox profile") {
                Text("Sign in to sites in Jeff's dedicated profile. The first version is read-only: it will not click buttons, fill forms, or submit anything.")
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            if !model.browserRunning {
                Button("Start Jeff's Firefox", systemImage: "play.fill") {
                    Task { await model.startBrowser() }
                }
                .buttonStyle(.borderedProminent)
            } else {
                HStack {
                    TextField("https://example.com", text: $address)
                        .textFieldStyle(.roundedBorder)
                    Button("Open page") {
                        Task { await model.navigateBrowser(to: address) }
                    }
                    .buttonStyle(.borderedProminent)
                    Button("Read visible text") {
                        Task { await model.readBrowserPage() }
                    }
                }
                if let page = model.browserPage {
                    Text(page.title.isEmpty ? page.url : page.title)
                        .font(.headline)
                    Text(page.url)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    TextEditor(text: .constant(page.text))
                        .font(.callout)
                        .frame(minHeight: 180)
                        .disabled(true)
                    HStack {
                        Button(model.browserContextAdded ? "Remove from next chat" : "Add to next chat") {
                            model.browserContextAdded.toggle()
                        }
                        .buttonStyle(.bordered)
                        Button("Stop Firefox", role: .destructive) {
                            Task { await model.stopBrowser() }
                        }
                    }
                }
            }
            Spacer()
        }
        .padding(24)
        .navigationTitle("Browser")
    }
}

private struct VPNView: View {
    @EnvironmentObject private var model: JeffModel

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("VPN").font(.largeTitle.bold())
                Spacer()
                Button("Refresh", systemImage: "arrow.clockwise") {
                    Task { await model.refreshVPN() }
                }
            }
            Text("Jeff controls OpenVPN Connect profiles registered with macOS. Connect and disconnect actions change the Mac's VPN for all apps.")
                .foregroundStyle(.secondary)
            if model.vpnConnections.isEmpty {
                VStack(spacing: 10) {
                    Image(systemName: "lock.shield")
                        .font(.largeTitle)
                        .foregroundStyle(.secondary)
                    Text("No OpenVPN profiles found")
                        .font(.title2.weight(.semibold))
                    Text("Install OpenVPN Connect and add a profile, then refresh.")
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, minHeight: 300)
            } else {
                List(model.vpnConnections) { connection in
                    HStack {
                        VStack(alignment: .leading) {
                            Text(connection.label).font(.headline)
                            Text(connection.status).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if connection.status.caseInsensitiveCompare("Connected") == .orderedSame {
                            Button("Disconnect", role: .destructive) {
                                model.askToChangeVPN("disconnect", connection: connection)
                            }
                        } else {
                            Button("Connect") {
                                model.askToChangeVPN("connect", connection: connection)
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }
                }
            }
            Spacer()
        }
        .padding(24)
        .navigationTitle("VPN")
        .task { await model.refreshVPN() }
    }
}

private struct SettingsView: View {
    @EnvironmentObject private var model: JeffModel

    private let moods = [
        "😊 Happy",
        "😌 Calm",
        "🤔 Curious",
        "😕 Stressed",
        "😞 Sad",
        "😴 Tired",
    ]
    private let languages = [
        "Auto (match my message)",
        "English",
        "French",
    ]

    var body: some View {
        Form {
            Text("Settings").font(.largeTitle.bold())
            Section("Ollama connection") {
                TextField("Server address", text: $model.settings.ollamaURL)
                TextField("Chat model", text: $model.settings.chatModel)
                TextField("Embedding model", text: $model.settings.embeddingModel)
                Text("For privacy, Jeff accepts only an Ollama server running on this Mac.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Button("Check connection and models") {
                    Task { await model.checkModels() }
                }
                .buttonStyle(.borderedProminent)
                if let status = model.modelStatus {
                    LabeledContent("Ollama", value: status.reachable ? "Reachable" : "Not reachable")
                    LabeledContent(
                        "Chat model \(model.settings.chatModel)",
                        value: status.chatModelPresent ? "Available" : "Not found"
                    )
                    LabeledContent(
                        "Embedding model \(model.settings.embeddingModel)",
                        value: status.embeddingModelPresent ? "Available" : "Not found"
                    )
                    if !status.chatModelPresent || !status.embeddingModelPresent {
                        Text("Install a missing model with `ollama pull <model name>` in Terminal.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            Section("How Jeff replies") {
                Picker("Mood", selection: $model.settings.mood) {
                    ForEach(moods, id: \.self) { Text($0) }
                }
                Picker("Reply language", selection: $model.settings.replyLanguage) {
                    ForEach(languages, id: \.self) { Text($0) }
                }
                Text("Jeff is currently set up to reply in English or French. Automatic language detection and model quality can vary.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Section("Privacy") {
                Text("Chat prompts, selected glossary entries, document excerpts, and browser text you explicitly add to a chat are sent to the configured local Ollama server. The glossary stays on this Mac. Chat history and document indexes stay in this app session.")
                Text("Jeff's native window does not open a browser. Firefox Developer Edition and OpenVPN Connect are separate optional integrations.")
            }
        }
        .formStyle(.grouped)
        .padding(12)
        .navigationTitle("Settings")
    }
}
