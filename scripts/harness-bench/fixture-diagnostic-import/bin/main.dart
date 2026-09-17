import 'package:collection/collections.dart';

void main() {
  final valeurs = [3, 1, 2];
  print(valeurs.sorted((a, b) => a.compareTo(b)));
}
