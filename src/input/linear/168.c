int unknown();
/*@ requires (x + y) == k; */
void foo168(int k, int x, int y) {

    int j;
    int i;
    int n;
    int m;

    m = 0;
    j = 0;
    n = unknown();
    i = unknown();


    while(j < n){
       if(j == i){
       x = x + 1;
       y = y - 1;
       j = j + 1;
       if(unknown()){
       m = j;
      }
      }
       else if(j != i){
       x = x - 1;
       y = y + 1;
       j = j + 1;
       if(unknown()){
       m = j;
      }
      }

      }

    /*@ assert (j >= n && n > 0) ==> (0 <= m); */

  }