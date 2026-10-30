// util/usage.hh pour WebAssembly : des mesures de temps et de mémoire dont
// seuls les programmes de KenLM se servent, jamais la lecture d'un modèle.
#include "util/usage.hh"

#include <chrono>
#include <cstdlib>
#include <ostream>

namespace util {

double WallTime() {
  using namespace std::chrono;
  return duration<double>(steady_clock::now().time_since_epoch()).count();
}

double CPUTime() { return 0.0; }
double ThreadTime() { return 0.0; }
uint64_t RSSMax() { return 0; }
void PrintUsage(std::ostream &) {}
uint64_t GuessPhysicalMemory() { return 0; }
uint64_t ParseSize(const std::string &arg) { return std::strtoull(arg.c_str(), nullptr, 10); }

}  // namespace util
