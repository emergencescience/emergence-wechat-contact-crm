import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1 else {
    print("Usage: mac_ocr_fast <image_path_1> [image_path_2 ...]")
    exit(1)
}

let imagePaths = Array(CommandLine.arguments.dropFirst())

// Multithreaded concurrent queue utilizing Apple Silicon CPU/GPU cores
let queue = OperationQueue()
queue.maxConcurrentOperationCount = 8

let lock = NSLock()

for imagePath in imagePaths {
    queue.addOperation {
        let fileURL = URL(fileURLWithPath: imagePath)
        guard let image = NSImage(contentsOf: fileURL),
              let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
            return
        }
        
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"]
        request.usesLanguageCorrection = false
        
        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        do {
            try handler.perform([request])
            guard let observations = request.results else { return }
            
            // Sort top to bottom (origin.y = 1 is top, 0 is bottom in Vision coordinates)
            let sorted = observations.sorted { $0.boundingBox.origin.y > $1.boundingBox.origin.y }
            var frameTexts: [String] = []
            for obs in sorted {
                if let candidate = obs.topCandidates(1).first {
                    let t = candidate.string.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !t.isEmpty {
                        frameTexts.append(t)
                    }
                }
            }
            
            lock.lock()
            let fname = (imagePath as NSString).lastPathComponent
            let jsonPayload: [String: Any] = [
                "file": fname,
                "contacts": frameTexts
            ]
            if let jsonData = try? JSONSerialization.data(withJSONObject: jsonPayload, options: []),
               let jsonString = String(data: jsonData, encoding: .utf8) {
                print(jsonString)
                fflush(stdout)
            }
            lock.unlock()
        } catch {
            return
        }
    }
}

queue.waitUntilAllOperationsAreFinished()
