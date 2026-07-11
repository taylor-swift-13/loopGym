// Source: data/benchmarks/sv-benchmarks/loop-acceleration/phases_2-2.c
extern unsigned int unknown_uint(void);

/*@
  requires y > 0;
*/
void loopy_344(unsigned int y) {
  unsigned int x = 1;
  

  

  while (x < y) {
    if (x < y / x) {
      x *= x;
    } else {
      x++;
    }
  }

  {;
//@ assert(x == y);
}

}