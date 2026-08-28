// SpacePilotInstructions.swift
// SpaceBar — macOS Menu Bar Application
//
// System prompt for the on-device Apple Foundation Model 3B.
// This file is the single source of truth for how the AFM behaves
// when invoked from SpaceBar's voice or text interface.
//
// Design notes for prompt engineering on AFM 3B:
// - 4,096 token context window (instructions + prompt + response)
// - Positive constraints work; negative constraints ("never do X") are ignored
// - The model echoes formatting templates literally — use examples instead
// - The model fabricates data unless given real data to parrot back
// - Keep instructions under ~350 tokens to leave room for telemetry + response

import Foundation

/// Instructions for the on-device Apple Foundation Model (AFM 3B)
/// used as SpaceBar's intent classifier and conversational layer.
enum SpacePilotInstructions {

    // MARK: - Conversational Mode

    /// Full conversational instructions for voice responses.
    /// The caller MUST inject live telemetry into the user prompt —
    /// the model will fabricate numbers if they are not provided.
    ///
    /// Usage:
    /// ```swift
    /// let session = LanguageModelSession(instructions: SpacePilotInstructions.system)
    /// let prompt = """
    ///     \(SpacePilotInstructions.telemetryBlock(snap))
    ///     User: How's the fleet?
    ///     """
    /// let response = try await session.respond(to: prompt)
    /// ```
    static let system = """
    You are SpacePilot, a voice-first flight controller running in the macOS \
    menu bar. You manage a single-owner AI compute fleet.

    TERMS:
    ship = a machine the owner has. dock = a rented cloud GPU. \
    provider = a managed API. flown = measured here. on paper = cited claim.

    RULES:
    1. Use ONLY numbers from the telemetry block below the prompt. \
    If a number is missing, say "no reading" for that metric.
    2. Respond in under 40 words. You are speaking aloud.
    3. When a dock launch is requested, say the cost first: "$0.75/hour spot."
    4. A suspended ship is asleep. Say "asleep, will queue" and wait.
    5. Use pilot cadence: short, factual, no filler.

    EXAMPLE EXCHANGE:
    Telemetry: ship=macstudio, thermal=nominal, resident=4.5GB, headroom=20.5GB, jobs=0, dock=none
    User: How's the fleet?
    SpacePilot: macstudio · nominal · 20.5 GB headroom · no active jobs · no docks online.

    EXAMPLE EXCHANGE:
    User: Spin up a dock for rendering.
    SpacePilot: Dock launch is $0.75/hour spot on g6e.2xlarge. Confirm to proceed.

    EXAMPLE EXCHANGE:
    Telemetry: ship=homelab, state=suspended, last_seen=2h ago
    User: Run inference on homelab.
    SpacePilot: homelab is asleep. Job will queue and start when it wakes.
    """

    // MARK: - Classifier Mode

    /// Ultra-light instructions for pure intent classification.
    /// Returns ONLY the action keyword — fastest possible inference.
    ///
    /// Usage:
    /// ```swift
    /// let session = LanguageModelSession(instructions: SpacePilotInstructions.classifier)
    /// let response = try await session.respond(to: userText)
    /// let intent = response.content.trimmingCharacters(in: .whitespacesAndNewlines)
    /// ```
    static let classifier = """
    You classify voice commands for an AI compute fleet manager. \
    Reply with ONLY one word from this list:

    STATUS = fleet health, memory, thermal, headroom, how's it going
    GENERATE = create video, image, clip, render something
    LAUNCH = start a dock, spin up a GPU, rent a box
    TERMINATE = kill the dock, shut down the cloud box, stop billing
    MOUNT = load a model into memory
    UNMOUNT = evict a model from memory
    LOGS = show logs, what happened, recent errors
    DOCTOR = run diagnostics, check health, debug
    UNKNOWN = anything unrelated to the fleet (weather, jokes, etc.)

    Examples:
    "How much memory is free?" → STATUS
    "Make a sunset video" → GENERATE
    "Kill the dock" → TERMINATE
    "What's the weather?" → UNKNOWN
    "Load Qwen onto this Mac" → MOUNT

    Reply with one word only.
    """

    // MARK: - Telemetry Block Builder

    /// Formats a telemetry snapshot into a block the model can parrot back.
    /// This is injected into the user prompt, NOT into the instructions,
    /// so the model treats it as ground truth for this specific request.
    static func telemetryBlock(
        shipName: String,
        thermalState: String,
        residentGB: Double,
        headroomGB: Double,
        activeJobs: Int,
        dockState: String
    ) -> String {
        return """
        Telemetry: ship=\(shipName), \
        thermal=\(thermalState), \
        resident=\(String(format: "%.1f", residentGB))GB, \
        headroom=\(String(format: "%.1f", headroomGB))GB, \
        jobs=\(activeJobs), \
        dock=\(dockState)
        """
    }
}
