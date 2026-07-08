/*@ requires n > 0 && n <= 20000001; */
void foo316(unsigned int n) {
    unsigned int j;
    unsigned int i;
    unsigned int k;

    i = 0;
    k = 0;
    j = 0;


    while (i < n) {
       i = i + 3;
       j = j + 3;
       k = k + 3;
      }

    /*@ assert (n > 0 && n <= 20000001) ==> (i % (20000003)); */

  }