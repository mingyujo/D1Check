
#include <locale.h>
namespace flatbuffers {
class ClassicLocale {
  typedef locale_t locale_type;
  locale_type locale_;
  static ClassicLocale instance_;
  ClassicLocale();
  ~ClassicLocale();
 public:
  static const locale_type &Get() { return instance_.locale_; }
};
ClassicLocale::ClassicLocale() { locale_ = newlocale(LC_ALL, "C", nullptr); }
ClassicLocale::~ClassicLocale() { freelocale(locale_); }
ClassicLocale ClassicLocale::instance_;
}  // namespace flatbuffers
