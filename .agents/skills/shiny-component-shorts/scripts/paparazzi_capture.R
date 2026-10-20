# Paparazzi owns capture; Python shares its browser and the existing action runner.
# Only public paparazzi/chromote APIs are used. No pause/hold splices are allowed.
args <- commandArgs(trailingOnly = TRUE)
config <- jsonlite::read_json(args[[1]], simplifyVector = TRUE)
if (!requireNamespace("paparazzi", quietly = TRUE) || !requireNamespace("av", quietly = TRUE)) {
  stop("Install paparazzi and av in an R library, then set R_LIBS_USER to that library.")
}
library(paparazzi)
write_state <- function(name, value) {
  path <- file.path(config$control_dir, paste0(name, ".json"))
  jsonlite::write_json(value, paste0(path, ".tmp"), auto_unbox = TRUE, digits = NA)
  file.rename(paste0(path, ".tmp"), path)
}
main <- function() {
  page <- pz_open("about:blank", width = config$width, height = config$height,
                  scale = 2, wait = "none")
  on.exit(pz_close(page), add = TRUE)
  session <- pz_chromote(page)
  write_state("ready", list(endpoint = session$parent$url(),
                            target = session$get_target_id(),
                            version = as.character(packageVersion("paparazzi"))))
  deadline <- Sys.time() + 120
  while (!file.exists(file.path(config$control_dir, "start"))) {
    if (Sys.time() > deadline) stop("Timed out waiting for the action runner")
    pz_wait(page, 0.02)
  }
  ctx <- pz_record_start(page, config$output, method = "poll", fps = 30,
                          hold = c(0, 0), captions = "vtt")
  before <- as.numeric(Sys.time())
  pz_annotate_caption(ctx, "shorts-clock")
  after <- as.numeric(Sys.time())
  # The VTT sidecar supplies this marker's actual time in the exported video.
  write_state("started", list(epoch = (before + after) / 2,
                              clock_uncertainty_seconds = (after - before) / 2))
  deadline <- Sys.time() + config$timeout
  while (!file.exists(file.path(config$control_dir, "stop"))) {
    if (Sys.time() > deadline) stop("Timed out waiting for recording completion")
    pz_wait(ctx, 0.01)
  }
  pz_record_stop(ctx)
  write_state("stopped", list(ok = TRUE))
}
main()
