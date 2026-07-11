// Source: data/benchmarks/sv-benchmarks/loop-acceleration/simple_3-2.c
extern unsigned int unknown_ushort(void);

/*@
  requires N <= 65535;
*/
void loopy_347(unsigned int N) {
  unsigned int x = 0;
  

  while (x < N) {
    x += 2;
  }

  {;
//@ assert(!(x % 2));
}

}